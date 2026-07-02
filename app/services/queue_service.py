from app.extensions import db
from app.models import (QueueToken, ServiceType, Customer,
                         TokenStatus, PriorityReason, Branch)
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


class QueueService:

    @staticmethod
    def generate_token_number(branch_id: int, service_type_id: int) -> str:
        service = ServiceType.query.get(service_type_id)
        today   = date.today()
        last    = (QueueToken.query
                   .filter_by(branch_id=branch_id,
                               service_type_id=service_type_id,
                               queue_date=today)
                   .order_by(QueueToken.id.desc())
                   .with_for_update()
                   .first())
        seq = (int(last.token_number[len(service.prefix):]) + 1) if last else 1
        return f"{service.prefix}{seq:03d}"

    @staticmethod
    def get_position(token: QueueToken) -> int:
        """How many people are ahead in the same service queue."""
        return (QueueToken.query
                .filter_by(branch_id=token.branch_id,
                            service_type_id=token.service_type_id,
                            queue_date=token.queue_date,
                            status=TokenStatus.WAITING)
                .filter(QueueToken.is_priority >= token.is_priority,
                        QueueToken.id < token.id)
                .count())

    @staticmethod
    def get_now_serving(branch_id: int) -> list:
        """Tokens currently called or being served."""
        return (QueueToken.query
                .filter(QueueToken.branch_id == branch_id,
                        QueueToken.status.in_([TokenStatus.CALLED, TokenStatus.SERVING]),
                        QueueToken.queue_date == date.today())
                .all())

    @staticmethod
    def register_customer(branch_id: int, full_name: str, mobile: str,
                           service_type_id: int, custom_reason: str = None,
                           is_priority: bool = False,
                           priority_reason: PriorityReason = PriorityReason.NONE) -> QueueToken:
        from app.services.sms_service import SmsService

        # Normalise mobile
        mobile = SmsService.normalise_mobile(mobile.strip())

        # Upsert customer
        customer = Customer.query.filter_by(mobile=mobile).first()
        if not customer:
            customer = Customer(full_name=full_name.strip(), mobile=mobile)
            db.session.add(customer)
            db.session.flush()
        else:
            customer.full_name = full_name.strip()  # update name if changed

        token_number = QueueService.generate_token_number(branch_id, service_type_id)
        service      = ServiceType.query.get(service_type_id)

        token = QueueToken(
            branch_id=branch_id,
            customer_id=customer.id,
            service_type_id=service_type_id,
            token_number=token_number,
            custom_reason=custom_reason,
            is_priority=is_priority,
            priority_reason=priority_reason,
            queue_date=date.today(),
        )
        db.session.add(token)
        db.session.commit()

        position = QueueService.get_position(token)
        token.estimated_wait_min = position * service.avg_service_min
        db.session.commit()

        # Send confirmation SMS (async)
        try:
            SmsService.send_confirmation(token)
        except Exception as e:
            logger.warning(f"SMS confirmation failed for token {token.id}: {e}")

        # Push real-time update
        try:
            from app.services.notification_service import push_queue_update
            push_queue_update(branch_id)
        except Exception:
            pass

        return token

    @staticmethod
    def call_next(officer_user, counter_id: int) -> QueueToken:
        """
        Call the next eligible customer for this officer's role.
        Priority customers always come first, then FIFO.
        """
        branch_id   = officer_user.branch_id
        today       = date.today()
        service_ids = [s.id for s in ServiceType.query.filter(
            ServiceType.code.in_(officer_user.allowed_service_codes)).all()]

        # Priority first, then FIFO within same service type
        token = (QueueToken.query
                 .filter(QueueToken.branch_id == branch_id,
                         QueueToken.status == TokenStatus.WAITING,
                         QueueToken.queue_date == today,
                         QueueToken.service_type_id.in_(service_ids))
                 .order_by(QueueToken.is_priority.desc(), QueueToken.id.asc())
                 .first())

        if not token:
            return None

        token.status     = TokenStatus.CALLED
        token.counter_id = counter_id
        token.served_by  = officer_user.id
        token.called_at  = datetime.utcnow()
        db.session.commit()

        # Send call notification SMS
        try:
            from app.services.sms_service import SmsService
            SmsService.send_call_notification(token)
        except Exception as e:
            logger.warning(f"SMS call notification failed for token {token.id}: {e}")

        # Push WebSocket update
        try:
            from app.services.notification_service import push_queue_update
            push_queue_update(branch_id)
        except Exception:
            pass

        return token

    @staticmethod
    def start_service(token_id: int, officer_user) -> QueueToken:
        token = QueueToken.query.get_or_404(token_id)
        token.status   = TokenStatus.SERVING
        token.served_at = datetime.utcnow()
        db.session.commit()
        return token

    @staticmethod
    def complete_service(token_id: int, officer_user) -> QueueToken:
        token = QueueToken.query.get_or_404(token_id)
        token.status       = TokenStatus.COMPLETED
        token.completed_at = datetime.utcnow()
        if not token.served_at:
            token.served_at = datetime.utcnow()
        db.session.commit()
        try:
            from app.services.notification_service import push_queue_update
            push_queue_update(token.branch_id)
        except Exception:
            pass
        return token

    @staticmethod
    def mark_no_show(token_id: int) -> QueueToken:
        token = QueueToken.query.get_or_404(token_id)
        token.status       = TokenStatus.NO_SHOW
        token.completed_at = datetime.utcnow()
        db.session.commit()
        try:
            from app.services.notification_service import push_queue_update
            push_queue_update(token.branch_id)
        except Exception:
            pass
        return token

    @staticmethod
    def upgrade_priority(token_id: int, reason: str) -> QueueToken:
        token = QueueToken.query.get_or_404(token_id)
        token.is_priority    = True
        token.priority_reason = PriorityReason[reason.upper()]
        db.session.commit()
        return token
