import os
import time
from typing import Dict, Any

class EmailService:
    def __init__(self):
        self.smtp_host = os.environ.get("SMTP_HOST", "")
        self.smtp_user = os.environ.get("SMTP_USER", "")
        self.demo_mode = os.environ.get("DEMO_ALERT_MODE", "true").lower() == "true"

    def get_status(self) -> str:
        if self.demo_mode:
            return "SIMULATED"
        if not self.smtp_host:
            return "NOT_CONFIGURED"
        return "AVAILABLE"

    def send_email(self, to_email: str, subject: str, message: str) -> Dict[str, Any]:
        if self.demo_mode:
            return {
                "status": "SIMULATED",
                "provider_message_id": None,
                "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            
        if not self.smtp_host:
            return {
                "status": "FAILED",
                "failure_reason": "NOT_CONFIGURED",
                "provider_message_id": None
            }
            
        # Real integration would go here
        return {
            "status": "SENT",
            "provider_message_id": f"email-msg-{int(time.time())}",
            "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

email_service = EmailService()
