import logging
from app.extensions import db
from app.models import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    @staticmethod
    def log(user_id, action: str, payload: dict = None, token_id: int = None):
        try:
            from flask import request
            ip = request.remote_addr if request else None
        except RuntimeError:
            ip = None

        entry = AuditLog(
            user_id=user_id,
            token_id=token_id,
            action=action,
            payload=payload or {},
            ip_address=ip,
        )
        try:
            db.session.add(entry)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"AuditService.log failed: {e}")
