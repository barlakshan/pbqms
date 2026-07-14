import logging
from datetime import datetime, timezone
from app.extensions import db

logger = logging.getLogger(__name__)

try:
    from celery import Celery, shared_task

    @shared_task(bind=True, max_retries=3, default_retry_delay=30)
    def send_sms_async(self, mobile: str, message: str, token_id: int, sms_type: str):
        """Celery task: send an SMS and log the result."""
        from app.models import SmsLog, SmsType, SmsStatus
        from app.services.sms_service import SmsService

        try:
            # Check if log already exists to avoid duplicates
            log = SmsLog.query.filter_by(
                token_id=token_id,
                sms_type=SmsType[sms_type.upper()],
                mobile=mobile
            ).first()
            
            if not log:
                log = SmsLog(
                    token_id=token_id,
                    sms_type=SmsType[sms_type.upper()],
                    mobile=mobile,
                    message=message,
                    status=SmsStatus.PENDING,
                )
                db.session.add(log)
                db.session.commit()

            result = SmsService._dispatch(mobile, message)
            log.status              = SmsStatus.SENT
            log.provider_message_id = result.get("message_id", "")
            log.sent_at             = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(f"SMS sent to {mobile} | type={sms_type} | id={result.get('message_id')}")
            return {"status": "sent", "message_id": result.get("message_id")}
            
        except Exception as exc:
            logger.warning(f"SMS send attempt failed for {mobile}: {exc}. Retrying...")
            try:
                if log:
                    log.status = SmsStatus.FAILED
                    db.session.commit()
            except Exception as db_err:
                logger.error(f"Failed to update SMS log status: {db_err}")
                db.session.rollback()
            
            # Retry with exponential backoff
            try:
                raise self.retry(exc=exc, countdown=60)
            except Exception as retry_err:
                logger.error(f"Max retries exceeded for SMS to {mobile}: {retry_err}")
                return {"status": "failed", "error": str(exc)}

except ImportError:
    # Celery not installed or not configured — stub
    def send_sms_async(*args, **kwargs):
        logger.warning("Celery not available — SMS queued via thread")
