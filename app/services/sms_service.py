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
        celery_used = False
        try:
            from app.tasks.sms_tasks import send_sms_async
            send_sms_async.delay(mobile=mobile, message=message,
                                  token_id=token_id, sms_type=sms_type)
            celery_used = True
            logger.debug(f"SMS queued via Celery for {mobile}")
        except Exception as celery_err:
            # Celery not running or error — use background thread
            logger.warning(f"Celery unavailable ({celery_err}), falling back to threading for SMS")
            try:
                app = current_app._get_current_object()
                t = threading.Thread(
                    target=cls._thread_send,
                    args=(app, mobile, message, token_id, sms_type),
                    daemon=True,
                )
                t.start()
                logger.debug(f"SMS queued via thread for {mobile}")
            except Exception as thread_err:
                logger.error(f"Failed to queue SMS via both Celery and thread: {thread_err}")

    @classmethod
    def _thread_send(cls, app, mobile, message, token_id, sms_type):
        with app.app_context():
            from app.extensions import db
            from app.models import SmsLog, SmsType, SmsStatus
            from datetime import datetime, timezone
            
            # Create log entry first
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
                log.sent_at             = datetime.now(timezone.utc)
                logger.info(f"SMS sent to {mobile} | type={sms_type} | id={result.get('message_id')}")
            except Exception as e:
                log.status = SmsStatus.FAILED
                logger.error(f"SMS send failed to {mobile}: {e}", exc_info=True)
            finally:
                try:
                    db.session.commit()
                except Exception as db_err:
                    logger.error(f"Failed to update SMS log: {db_err}")
                    db.session.rollback()

    @staticmethod
    def _normalize_provider(provider: str | None) -> str:
        if not provider:
            return "mock"

        provider = str(provider).strip().lower()
        if provider.startswith(("http://", "https://")):
            if "text.lk" in provider or "textlk" in provider:
                return "textlk"
            if "dialog" in provider:
                return "dialog"
            if "mobitel" in provider:
                return "mobitel"
            if "twilio" in provider:
                return "twilio"
            return "mock"

        if provider in {"textlk", "text.lk", "text-lk", "text_lk", "text"}:
            return "textlk"
        if provider in {"mock", "none", "off", "disabled"}:
            return "mock"

        return provider

    @classmethod
    def _dispatch(cls, mobile: str, message: str) -> dict:
        provider = cls._normalize_provider(current_app.config.get("SMS_PROVIDER", "mock"))

        if provider == "dialog":
            return cls._dialog(mobile, message)
        elif provider == "mobitel":
            return cls._mobitel(mobile, message)
        elif provider == "textlk":
            return cls._textlk(mobile, message)
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
    def _textlk(cls, mobile: str, message: str) -> dict:
        """
        Send SMS using Text.lk API: https://app.text.lk/api/v3/sms/send
        Expects `TEXTLK_API_TOKEN` in app config and optional `TEXTLK_SENDER_ID`.
        Returns a dict with at least `message_id` when available.
        """
        token = current_app.config.get("TEXTLK_API_TOKEN")
        if not token:
            raise RuntimeError("TEXTLK_API_TOKEN not configured")

        sender = current_app.config.get("TEXTLK_SENDER_ID", "PPLSBANK")

        # Normalise recipient to format like 94771234567 (no +)
        recipient = mobile.replace("+", "").replace(" ", "").replace("-", "")
        if recipient.startswith("0"):
            recipient = "94" + recipient[1:]

        try:
            resp = requests.post(
                "https://app.text.lk/api/v3/sms/send",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "recipient": recipient,
                    "sender_id": sender,
                    "type": "plain",
                    "message": message,
                },
                timeout=10,
            )
            
            logger.debug(f"Text.lk API response status: {resp.status_code}")
            
            # Handle HTTP errors
            if resp.status_code >= 400:
                resp_text = resp.text[:200]  # Log first 200 chars of response
                logger.error(f"Text.lk API error {resp.status_code}: {resp_text}")
                resp.raise_for_status()
            
            data = resp.json()
            logger.debug(f"Text.lk API response: {data}")
            
            # Try to extract a sensible message id from the API response
            message_id = ""
            status = "unknown"
            
            if isinstance(data, dict):
                # Check for success status
                status = data.get("status", data.get("code", "unknown"))
                
                # Common response formats from Text.lk
                if status == "success" or status == "200" or status == 200:
                    # Try to extract message_id from nested data
                    d = data.get("data")
                    if isinstance(d, dict):
                        message_id = d.get("uid") or d.get("id") or d.get("message_id") or str(d)
                    elif isinstance(d, str):
                        message_id = d
                    else:
                        # Fallback: use entire response as string
                        message_id = str(data.get("message_id", ""))
                    
                    # If still no message_id, try top-level fields
                    if not message_id:
                        message_id = data.get("message_id") or data.get("uid") or data.get("id") or ""
                    
                    if not message_id:
                        # Last resort: generate from timestamp
                        message_id = f"textlk-{int(__import__('time').time() * 1000)}"
                else:
                    # API returned error status
                    error_msg = data.get("message", data.get("error", str(data)))
                    logger.error(f"Text.lk API returned error status: {status} - {error_msg}")
                    raise RuntimeError(f"Text.lk API error: {error_msg}")

            return {"status": str(status), "message_id": message_id}
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Text.lk API request failed: {e}")
            raise RuntimeError(f"Text.lk API request failed: {e}")

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
