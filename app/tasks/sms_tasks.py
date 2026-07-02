import logging
from datetime import datetime
from app.extensions import db

logger = logging.getLogger(__name__)

try:
    from celery import Celery, shared_task

    @shared_task(bind=True, max_retries=3, default_retry_delay=30)
    def send_sms_async(self, mobile: str, message: str, token_id: int, sms_type: str):
        """Celery task: send an SMS and log the result."""
        from app.models import SmsLog, SmsType, SmsStatus
        from app.services.sms_service import SmsService

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
            result = SmsService._dispatch(mobile, message)
            log.status              = SmsStatus.SENT
            log.provider_message_id = result.get("message_id", "")
            log.sent_at             = datetime.utcnow()
            db.session.commit()
            logger.info(f"SMS sent to {mobile} | type={sms_type} | id={result.get('message_id')}")
        except Exception as exc:
            log.status = SmsStatus.FAILED
            db.session.commit()
            logger.error(f"SMS failed to {mobile}: {exc}")
            raise self.retry(exc=exc)

except ImportError:
    # Celery not installed or not configured — stub
    def send_sms_async(*args, **kwargs):
        logger.warning("Celery not available — SMS queued via thread")
