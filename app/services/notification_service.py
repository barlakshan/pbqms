import logging
from app.extensions import socketio
from app.models import QueueToken, TokenStatus
from datetime import date

logger = logging.getLogger(__name__)


def push_queue_update(branch_id: int):
    """Emit live queue state to all SocketIO clients watching this branch."""
    try:
        today = date.today()
        serving = (QueueToken.query
                   .filter(QueueToken.branch_id == branch_id,
                           QueueToken.status.in_([TokenStatus.CALLED, TokenStatus.SERVING]),
                           QueueToken.queue_date == today)
                   .all())
        waiting_count = (QueueToken.query
                         .filter_by(branch_id=branch_id,
                                     status=TokenStatus.WAITING,
                                     queue_date=today)
                         .count())
        waiting_next = (QueueToken.query
                        .filter_by(branch_id=branch_id,
                                    status=TokenStatus.WAITING,
                                    queue_date=today)
                        .order_by(QueueToken.is_priority.desc(), QueueToken.id.asc())
                        .limit(5).all())

        payload = {
            "branch_id":     branch_id,
            "waiting_count": waiting_count,
            "serving": [{
                "token":           t.token_number,
                "customer_name":   t.customer.full_name,
                "counter":         t.counter.label if t.counter else "",
                "service":         t.service_type.name,
                "service_code":    t.service_type.code,
                "is_priority":     t.is_priority,
                "priority_reason": t.priority_reason.value if t.is_priority else "none",
            } for t in serving],
            "next": [{
                "token":        t.token_number,
                "service":      t.service_type.name,
                "service_code": t.service_type.code,
                "is_priority":  t.is_priority,
            } for t in waiting_next],
        }
        socketio.emit("queue_update", payload, room=f"branch_{branch_id}")
        logger.debug(f"Pushed queue update for branch {branch_id}: {waiting_count} waiting")
    except Exception as e:
        logger.error(f"push_queue_update failed: {e}")
