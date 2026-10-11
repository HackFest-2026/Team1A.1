from typing import Dict, Any, List, Optional
from datetime import datetime
from .models import Evidence, FieldReport
from .evidence_analysis_service import evidence_analysis_service
from .reassessment_service import reassessment_service
from ..incidents.incident_service import incident_service

class EvidenceService:
    """LEGACY in-memory field evidence (pre-Phase 4A). Not shown in the COP.

    Not migrated to the canonical store: the canonical schema requires a numeric
    source confidence that these records do not have (ai_confidence is mock random
    output), file_path is a placeholder, and records do not survive restarts. See
    docs/project/DECISIONS_AND_ROADMAP.md (ADR-010) for the retirement plan.
    """

    def __init__(self):
        self.evidence: Dict[str, Evidence] = {}
        self.reports: Dict[str, FieldReport] = {}

    def get_evidence_for_incident(self, incident_id: str) -> List[Dict[str, Any]]:
        return [e.dict() for e in self.evidence.values() if e.incident_id == incident_id]

    def add_evidence(self, evidence: Evidence) -> Evidence:
        self.evidence[evidence.evidence_id] = evidence
        incident_service._log_audit("SYSTEM", "SYSTEM", "EVIDENCE_UPLOADED", evidence.evidence_id, "SUCCESS")
        
        inc = incident_service.incidents.get(evidence.incident_id)
        if inc:
            incident_service._add_timeline(inc, "EVIDENCE_UPLOADED", f"Evidence {evidence.file_name} uploaded", "SYSTEM", "SYSTEM")
            
        return evidence

    def analyze_evidence(self, evidence_id: str) -> Dict[str, Any]:
        ev = self.evidence.get(evidence_id)
        if not ev: return {"error": "Evidence not found"}
        
        res = evidence_analysis_service.analyze(ev)
        incident_service._log_audit("SYSTEM", "SYSTEM", "EVIDENCE_ANALYZED", evidence_id, "SUCCESS")
        return {"status": "success", "evidence": ev.dict()}

    def confirm_evidence(self, evidence_id: str, confirmation: str, actor: str = "EOC_OPERATOR") -> Dict[str, Any]:
        ev = self.evidence.get(evidence_id)
        if not ev: return {"error": "Evidence not found"}
        
        if confirmation not in ["CONFIRMED", "REJECTED"]:
            return {"error": "Invalid confirmation status"}
            
        ev.human_confirmation = confirmation
        ev.confirmed_by = actor
        ev.confirmed_at = datetime.utcnow().isoformat() + "Z"
        
        status = "EVIDENCE_CONFIRMED" if confirmation == "CONFIRMED" else "EVIDENCE_REJECTED"
        incident_service._log_audit(actor, "EOC_OPERATOR", status, evidence_id, "SUCCESS")
        
        # Trigger reassessment logic
        reassessment_service.check_reassessment(ev.incident_id, "EVIDENCE_CONFIRMATION", ev)
        
        return {"status": "success", "evidence": ev.dict()}

    def get_reports_for_incident(self, incident_id: str) -> List[Dict[str, Any]]:
        return [r.dict() for r in self.reports.values() if r.incident_id == incident_id]

    def add_report(self, report: FieldReport) -> FieldReport:
        self.reports[report.report_id] = report
        incident_service._log_audit(report.created_by, "FIELD_OPERATOR", "FIELD_REPORT_CREATED", report.report_id, "SUCCESS")
        
        reassessment_service.check_reassessment(report.incident_id, "FIELD_REPORT", report)
        return report

evidence_service = EvidenceService()
