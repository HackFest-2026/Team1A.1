import os
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta
import uuid

from .models import AlertRecord, DeliveryRecord, AuditLog, AuthorityEscalation
from .citizen_service import citizen_service
from .sms_service import sms_service
from .email_service import email_service
from ..national_risk_service import national_risk_service

class AlertDecisionService:
    def __init__(self):
        self.active_alerts: Dict[str, AlertRecord] = {}
        self.audit_logs: List[AuditLog] = []
        self.escalations: Dict[str, AuthorityEscalation] = {}

    def _log_audit(self, actor: str, action: str, alert_id: str, result: str):
        log = AuditLog(actor=actor, action=action, alert_id=alert_id, result=result)
        self.audit_logs.append(log)

    def preview_alert(self, state: str, district: str) -> Dict[str, Any]:
        risk_data = national_risk_service.get_national_risk(state, district)
        if risk_data.get("status") == "unavailable" or not risk_data.get("regions"):
            return {"error": "Risk data unavailable"}
        
        region = risk_data["regions"][0]
        
        imd_level = region.get("official_warning", {}).get("level", "NORMAL").upper()
        rr_level = region.get("risk", {}).get("level", "NORMAL").upper()
        
        # Decide Severity
        severity = "NORMAL"
        reason = ""
        
        if imd_level == "CRITICAL" or rr_level == "CRITICAL":
            severity = "CRITICAL"
            reason = "Official warning or ResilienceRoute risk is CRITICAL"
        elif imd_level == "HIGH" or rr_level == "HIGH":
            severity = "HIGH"
            reason = "Official warning or ResilienceRoute risk is HIGH"
        elif imd_level == "WARNING" or rr_level == "WARNING":
            severity = "WARNING"
            reason = "Elevated risk or official warning"
        elif imd_level == "WATCH" or rr_level == "WATCH":
            severity = "WATCH"
            reason = "Active watch"
            
        target_citizens = citizen_service.get_by_region(state, district)
        
        en_msg = f"RESILIENCEROUTE ALERT\nSeverity: {severity}\nRegion: {district}, {state}\nHazard: Flood / Weather Risk\nRisk Assessment: {region['risk']['score']}/100\nOfficial IMD Warning: {imd_level}\nRecommended action: Follow local authority instructions.\nSource: IMD + ResilienceRoute Risk Assessment (Prototype Decision-Support)"
        
        return {
            "target_region": {"state": state, "district": district},
            "severity": severity,
            "hazard_type": "Flood / Severe Weather",
            "reason": reason,
            "confidence": region.get("confidence", "UNKNOWN"),
            "data_freshness": region.get("freshness", "UNKNOWN"),
            "source": "IMD + ResilienceRoute",
            "messages": {"en": en_msg},
            "targeted_count": len(target_citizens),
            "sms_status": sms_service.get_status(),
            "email_status": email_service.get_status(),
            "expires_at": (datetime.utcnow() + timedelta(hours=6)).isoformat() + "Z"
        }

    def send_alert(self, preview_payload: Dict[str, Any], actor: str = "System") -> Dict[str, Any]:
        # Deduplication check
        state = preview_payload["target_region"]["state"]
        dist = preview_payload["target_region"]["district"]
        sev = preview_payload["severity"]
        
        for a in self.active_alerts.values():
            if a.status == "ACTIVE" and a.target_region.get("state") == state and a.target_region.get("district") == dist:
                if a.severity == sev:
                    # Prevent duplicate same-severity alert
                    return {"error": "Duplicate alert active for this region and severity."}
                
        # Create
        alert = AlertRecord(
            severity=sev,
            hazard_type=preview_payload["hazard_type"],
            target_region=preview_payload["target_region"],
            reason=preview_payload["reason"],
            confidence=preview_payload["confidence"],
            source=preview_payload["source"],
            messages=preview_payload["messages"],
            status="ACTIVE",
            expires_at=preview_payload["expires_at"],
            data_freshness=preview_payload["data_freshness"],
            targeted_count=preview_payload["targeted_count"]
        )
        self.active_alerts[alert.alert_id] = alert
        self._log_audit(actor, "ALERT_CREATED", alert.alert_id, "SUCCESS")

        target_citizens = citizen_service.get_by_region(state, dist)
        
        for c in target_citizens:
            if c.sms_enabled:
                sms_res = sms_service.send_sms(c.phone, alert.messages["en"])
                d = DeliveryRecord(alert_id=alert.alert_id, citizen_id=c.citizen_id, channel="SMS", status=sms_res["status"], provider_message_id=sms_res.get("provider_message_id"), failure_reason=sms_res.get("failure_reason"), sent_at=sms_res.get("sent_at"))
                alert.deliveries.append(d)
            if c.email_enabled:
                em_res = email_service.send_email(c.email, f"ResilienceRoute Alert: {sev}", alert.messages["en"])
                d = DeliveryRecord(alert_id=alert.alert_id, citizen_id=c.citizen_id, channel="EMAIL", status=em_res["status"], provider_message_id=em_res.get("provider_message_id"), failure_reason=em_res.get("failure_reason"), sent_at=em_res.get("sent_at"))
                alert.deliveries.append(d)
                
        self._log_audit(actor, "ALERT_SENT", alert.alert_id, "DELIVERIES_QUEUED")
        
        return {"alert_id": alert.alert_id, "status": "SENT", "deliveries": len(alert.deliveries)}

    def acknowledge_alert(self, alert_id: str, citizen_id: str) -> Dict[str, Any]:
        if alert_id not in self.active_alerts:
            return {"error": "Alert not found"}
        
        a = self.active_alerts[alert_id]
        updated = False
        for d in a.deliveries:
            if d.citizen_id == citizen_id and d.acknowledged_at is None:
                d.acknowledged_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                updated = True
        if updated:
            a.acknowledged_count += 1
            self._log_audit(citizen_id, "ALERT_ACKNOWLEDGED", alert_id, "SUCCESS")
            return {"status": "success"}
        return {"error": "Already acknowledged or citizen not found"}

    def escalate_authority(self, alert_id: str, action: str) -> Dict[str, Any]:
        if alert_id not in self.active_alerts:
            return {"error": "Alert not found"}
        a = self.active_alerts[alert_id]
        
        esc = AuthorityEscalation(
            alert_id=alert_id,
            region=a.target_region,
            severity=a.severity,
            recommended_action=action
        )
        self.escalations[esc.incident_id] = esc
        self._log_audit("EOC_OPERATOR", "ESCALATION_CREATED", alert_id, f"Escalated to Authority: {action}")
        return {"status": "success", "incident_id": esc.incident_id}

    def get_all(self):
        return [a.dict() for a in self.active_alerts.values()]

alert_decision_service = AlertDecisionService()
