import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task
    def daily_queue_reset():
        """Called by Celery Beat each morning at 07:00 to archive old tokens."""
        from app.extensions import db
        from app.models import QueueToken, TokenStatus
        yesterday = date.today() - timedelta(days=1)
        # Mark all still-waiting tokens from yesterday as skipped
        (QueueToken.query
         .filter_by(queue_date=yesterday, status=TokenStatus.WAITING)
         .update({"status": TokenStatus.SKIPPED}))
        db.session.commit()
        logger.info(f"Daily queue reset complete for {yesterday}")

except ImportError:
    pass
