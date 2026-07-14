from app.extensions import db
from app.models import (QueueToken, ServiceType, Customer,
                         TokenStatus, PriorityReason, Branch)
from datetime import date, datetime, timezone
import logging

logger = logging.getLogger(__name__)


class QueueService:

    @staticmethod
    def generate_token_number(branch_id: int, service_type_id: int) -> str:
        """Generate a unique token number for a service type on a given day."""
        service = ServiceType.query.get(service_type_id)
        if not service:
            raise ValueError(f"Service type {service_type_id} not found")
        
        today   = date.today()
        last    = (QueueToken.query
                   .filter_by(branch_id=branch_id,
                               service_type_id=service_type_id,
                               queue_date=today)
                   .order_by(QueueToken.id.desc())
                   .with_for_update()
                   .first())
        
        try:
            seq = (int(last.token_number[len(service.prefix):]) + 1) if last else 1
        except (ValueError, IndexError) as e:
            logger.error(f"Failed to parse token number: {last.token_number if last else 'None'}: {e}")
            seq = 1
        
        token_number = f"{service.prefix}{seq:03d}"
        logger.debug(f"Generated token: {token_number} for service {service.code}")
        return token_number

    @staticmethod
    def get_position(token: QueueToken) -> int:
        """How many people are ahead in the same service queue."""
        query = (QueueToken.query
                 .filter_by(branch_id=token.branch_id,
                            service_type_id=token.service_type_id,
                            queue_date=token.queue_date,
                            status=TokenStatus.WAITING)
                 .filter(QueueToken.id < token.id))

        if not token.is_priority:
            query = query.filter(QueueToken.is_priority.is_(False))

        return query.count()

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

        # Normalise and validate mobile
        try:
            mobile = SmsService.normalise_mobile(mobile.strip())
        except Exception as e:
            logger.error(f"Mobile normalization failed for {mobile}: {e}")
            raise ValueError(f"Invalid mobile number: {mobile}")

        # Upsert customer - handle duplicate mobile gracefully
        customer = Customer.query.filter_by(mobile=mobile).first()
        if not customer:
            customer = Customer(full_name=full_name.strip(), mobile=mobile)
            db.session.add(customer)
            db.session.flush()
        else:
            # Update name if this is a new customer registration
            if customer.full_name != full_name.strip():
                customer.full_name = full_name.strip()

        # Verify branch and service type exist
        branch = Branch.query.get(branch_id)
        if not branch or not branch.is_active:
            raise ValueError(f"Invalid or inactive branch: {branch_id}")
        
        service = ServiceType.query.get(service_type_id)
        if not service or not service.is_active:
            raise ValueError(f"Invalid or inactive service type: {service_type_id}")

        # Generate unique token number
        token_number = QueueService.generate_token_number(branch_id, service_type_id)

        # Create token
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

        # Calculate estimated wait
        position = QueueService.get_position(token)
        token.estimated_wait_min = position * service.avg_service_min
        db.session.commit()

        # Send confirmation SMS (async) - don't fail registration if SMS fails
        try:
            SmsService.send_confirmation(token)
        except Exception as e:
            logger.warning(f"SMS confirmation failed for token {token.id}: {e}")

        # Push real-time update
        try:
            from app.services.notification_service import push_queue_update
            push_queue_update(branch_id)
        except Exception as e:
            logger.warning(f"Failed to push queue update: {e}")

        logger.info(f"Customer registered: token={token.token_number}, mobile={mobile}")
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
        token.called_at  = datetime.now(timezone.utc)
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
        token.served_at = datetime.now(timezone.utc)
        db.session.commit()
        return token

    @staticmethod
    def complete_service(token_id: int, officer_user) -> QueueToken:
        token = QueueToken.query.get_or_404(token_id)
        token.status       = TokenStatus.COMPLETED
        token.completed_at = datetime.now(timezone.utc)
        if not token.served_at:
            token.served_at = datetime.now(timezone.utc)
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
        token.completed_at = datetime.now(timezone.utc)
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
