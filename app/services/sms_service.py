import requests
import threading
import logging
from flask import current_app

logger = logging.getLogger(__name__)


class SmsService:
    """
    SMS abstraction layer.
    Set SMS_PROVIDER in .env:  mock | dialog | mobitel | twilio
    """

    TEMPLATES = {
        "confirmation": (
            "Your People's Bank queue number is {token}. "
            "Service: {service}. Estimated wait: {wait} mins. "
            "Thank you for choosing People's Bank Sri Lanka."
        ),
        "call_notification": (
            "People's Bank: Token {token} - Please proceed to {counter}. "
            "Officer: {officer}. Branch: {branch}. Thank you."
        ),
    }

    @classmethod
    def send_confirmation(cls, token):
        message = cls.TEMPLATES["confirmation"].format(
            token=token.token_number,
            service=token.service_type.name,
            wait=token.estimated_wait_min,
        )
        cls._send_async(
            mobile=token.customer.mobile,
            message=message,
            token_id=token.id,
            sms_type="confirmation",
        )

    @classmethod
    def send_call_notification(cls, token):
        counter = token.counter.label if token.counter else "Counter"
        officer = token.served_by_officer.full_name if token.served_by_officer else ""
        message = cls.TEMPLATES["call_notification"].format(
            token=token.token_number,
            counter=counter,
            officer=officer,
            branch=token.branch.name,
        )
        cls._send_async(
            mobile=token.customer.mobile,
            message=message,
            token_id=token.id,
            sms_type="call_notification",
        )

    @classmethod
    def _send_async(cls, mobile, message, token_id, sms_type):
        """
        Try Celery first; fall back to a daemon thread if Celery not available.
        """
        try:
            from app.tasks.sms_tasks import send_sms_async
            send_sms_async.delay(mobile=mobile, message=message,
                                  token_id=token_id, sms_type=sms_type)
        except Exception:
            # Celery not running — use background thread
            app = current_app._get_current_object()
            t = threading.Thread(
                target=cls._thread_send,
                args=(app, mobile, message, token_id, sms_type),
                daemon=True,
            )
            t.start()

    @classmethod
    def _thread_send(cls, app, mobile, message, token_id, sms_type):
        with app.app_context():
            from app.extensions import db
            from app.models import SmsLog, SmsType, SmsStatus
            from datetime import datetime
            log = SmsLog(
                token_id=token_id,
                sms_type=SmsType[sms_type.upper()],
                mobile=mobile,
                message=message,
                status=SmsStatus.PENDING,
            )
            db.session.add(log)
            db.session.commit()
            try:
                result = cls._dispatch(mobile, message)
                log.status              = SmsStatus.SENT
                log.provider_message_id = result.get("message_id", "")
                log.sent_at             = datetime.utcnow()
            except Exception as e:
                log.status = SmsStatus.FAILED
                logger.error(f"SMS send failed to {mobile}: {e}")
            finally:
                db.session.commit()

    @classmethod
    def _dispatch(cls, mobile: str, message: str) -> dict:
        provider = current_app.config.get("SMS_PROVIDER", "mock")

        if provider == "dialog":
            return cls._dialog(mobile, message)
        elif provider == "mobitel":
            return cls._mobitel(mobile, message)
        elif provider == "twilio":
            return cls._twilio(mobile, message)
        else:
            logger.info(f"[SMS MOCK] To:{mobile} | {message}")
            return {"status": "sent", "message_id": "mock-001"}

    @classmethod
    def _dialog(cls, mobile: str, message: str) -> dict:
        # Normalise: remove + prefix for Dialog API
        m = mobile.replace("+", "").replace(" ", "")
        resp = requests.post(
            "https://sms.dialog.lk/api/send",
            json={
                "user": current_app.config["DIALOG_USER"],
                "pass": current_app.config["DIALOG_PASS"],
                "msisdn": m,
                "msg":    message,
                "sid":    current_app.config["DIALOG_SENDER_ID"],
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def _mobitel(cls, mobile: str, message: str) -> dict:
        resp = requests.post(
            "https://api.mobitel.lk/sms/send",  # confirm with Mobitel
            headers={
                "Authorization": f"Bearer {current_app.config['MOBITEL_TOKEN']}",
                "Content-Type":  "application/json",
            },
            json={
                "to":      mobile,
                "message": message,
                "from":    current_app.config.get("MOBITEL_SENDER_ID", "PPLSBANK"),
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def _twilio(cls, mobile: str, message: str) -> dict:
        from twilio.rest import Client
        client = Client(
            current_app.config["TWILIO_SID"],
            current_app.config["TWILIO_TOKEN"],
        )
        msg = client.messages.create(
            body=message,
            from_=current_app.config["TWILIO_FROM"],
            to=mobile,
        )
        return {"message_id": msg.sid}

    @staticmethod
    def normalise_mobile(mobile: str) -> str:
        """Ensure international format: +94771234567"""
        m = mobile.replace(" ", "").replace("-", "")
        if m.startswith("0"):
            return "+94" + m[1:]
        if not m.startswith("+"):
            return "+" + m
        return m
