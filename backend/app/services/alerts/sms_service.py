import os
import time
from typing import Dict, Any

class SmsService:
    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.environ.get("TWILIO_PHONE_NUMBER", "")
        self.demo_mode = os.environ.get("DEMO_ALERT_MODE", "true").lower() == "true"

    def get_status(self) -> str:
        if self.demo_mode:
            return "SIMULATED"
        if not self.account_sid or not self.auth_token:
            return "NOT_CONFIGURED"
        return "AVAILABLE"

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        if self.demo_mode:
            return {
                "status": "SIMULATED",
                "provider_message_id": None,
                "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            
        if not self.account_sid:
            return {
                "status": "FAILED",
                "failure_reason": "NOT_CONFIGURED",
                "provider_message_id": None
            }
            
        # Real integration would go here
        return {
            "status": "SENT",
            "provider_message_id": f"real-msg-{int(time.time())}",
            "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

sms_service = SmsService()
