from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid
from .models import CitizenAlert
from .citizen_service import citizen_service
from ..incidents.incident_service import incident_service

class AlertDeliveryService:
    def __init__(self):
        self.alerts: Dict[str, CitizenAlert] = {}

    def get_all(self, incident_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if incident_id:
            return [a.dict() for a in self.alerts.values() if a.incident_id == incident_id]
        return [a.dict() for a in self.alerts.values()]

    def create_alert(self, alert: CitizenAlert) -> CitizenAlert:
        self.alerts[alert.alert_id] = alert
        
        inc = incident_service.incidents.get(alert.incident_id)
        if inc:
            incident_service._add_timeline(inc, "ALERT_DRAFT_CREATED", f"Draft alert created for {alert.citizen_id}", "SYSTEM", "SYSTEM")
        
        incident_service._log_audit("SYSTEM", "SYSTEM", "ALERT_CREATED", alert.alert_id, "SUCCESS")
        return alert

    def approve_alert(self, alert_id: str, actor: str = "EOC_OPERATOR") -> Dict[str, Any]:
        alert = self.alerts.get(alert_id)
        if not alert: return {"error": "Alert not found"}
        
        if alert.status != "CREATED":
            return {"error": "Alert must be in CREATED state to approve"}
            
        alert.status = "APPROVED"
        alert.approved_at = datetime.utcnow().isoformat() + "Z"
        alert.approved_by = actor
        
        inc = incident_service.incidents.get(alert.incident_id)
        if inc:
            incident_service._add_timeline(inc, "ALERT_APPROVED", f"Alert {alert.alert_id} approved", actor, "EOC_OPERATOR")
            
        incident_service._log_audit(actor, "EOC_OPERATOR", "ALERT_APPROVED", alert_id, "SUCCESS")
        return {"status": "success", "alert": alert.dict()}

    def send_alert(self, alert_id: str) -> Dict[str, Any]:
        alert = self.alerts.get(alert_id)
        if not alert: return {"error": "Alert not found"}
        
        if alert.status != "APPROVED":
            return {"error": "Alert must be in APPROVED state to send"}
            
        citizen = citizen_service.get_citizen(alert.citizen_id)
        if not citizen:
            alert.status = "FAILED"
            alert.failure_reason = "Citizen not found"
            return {"error": alert.failure_reason}
            
        # Check consent
        if alert.channel in ["SMS", "BOTH"] and not citizen.consent_sms:
            alert.status = "FAILED"
            alert.failure_reason = "SMS_NOT_CONSENTED"
            return {"error": alert.failure_reason}
            
        if alert.channel in ["EMAIL", "BOTH"] and not citizen.consent_email:
            alert.status = "FAILED"
            alert.failure_reason = "EMAIL_NOT_CONSENTED"
            return {"error": alert.failure_reason}

        # Mock Send
        alert.status = "SENT"
        alert.sent_at = datetime.utcnow().isoformat() + "Z"
        alert.provider_message_id = f"MOCK-PROVIDER-{str(uuid.uuid4())[:8]}"
        
        inc = incident_service.incidents.get(alert.incident_id)
        if inc:
            incident_service._add_timeline(inc, "ALERT_SENT", f"Demo {alert.channel} sent to {alert.citizen_id}", "SYSTEM", "SYSTEM")
            
        incident_service._log_audit("SYSTEM", "SYSTEM", "ALERT_SENT", alert_id, "SUCCESS")
        
        # In a demo, we mock delivery automatically
        self.mock_delivery(alert_id)
        
        return {"status": "success", "alert": alert.dict(), "message": "TEST DELIVERY. NO PUBLIC ALERT SENT."}

    def mock_delivery(self, alert_id: str):
        alert = self.alerts.get(alert_id)
        if alert and alert.status == "SENT":
            alert.status = "DELIVERED"
            alert.delivered_at = datetime.utcnow().isoformat() + "Z"
            inc = incident_service.incidents.get(alert.incident_id)
            if inc:
                incident_service._add_timeline(inc, "ALERT_DELIVERED", f"Demo delivery confirmed for {alert.alert_id}", "SYSTEM", "SYSTEM")
            incident_service._log_audit("SYSTEM", "SYSTEM", "ALERT_DELIVERED", alert_id, "SUCCESS")

    def acknowledge_alert(self, alert_id: str) -> Dict[str, Any]:
        alert = self.alerts.get(alert_id)
        if not alert: return {"error": "Alert not found"}
        
        if alert.status == "ACKNOWLEDGED":
            return {"error": "Already acknowledged"}
            
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_at = datetime.utcnow().isoformat() + "Z"
        
        inc = incident_service.incidents.get(alert.incident_id)
        if inc:
            incident_service._add_timeline(inc, "ALERT_ACKNOWLEDGED", f"Citizen acknowledged alert {alert.alert_id}", "CITIZEN", "CITIZEN")
            
        incident_service._log_audit("CITIZEN", "CITIZEN", "ALERT_ACKNOWLEDGED", alert_id, "SUCCESS")
        return {"status": "success", "alert": alert.dict()}

alert_delivery_service = AlertDeliveryService()
