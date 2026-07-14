from flask import request, jsonify
from flask_login import login_required, current_user
from app.api import queue_bp
from app.services.queue_service import QueueService
from app.models import (PriorityReason, SatisfactionRating, QueueToken,
                          TokenStatus, UserRole, ServiceType, Branch, Counter)
from app.extensions import db
from app.utils.decorators import require_role, audit_action
from datetime import date


@queue_bp.get("/branch/<string:branch_code>/info")
def branch_info(branch_code):
    branch = Branch.query.filter_by(code=branch_code.upper(), is_active=True).first_or_404()
    waiting = QueueToken.query.filter(
        QueueToken.branch_id == branch.id,
        QueueToken.queue_date == date.today(),
        QueueToken.status.in_([TokenStatus.WAITING, TokenStatus.CALLED]),
    ).count()
    return jsonify({
        "id": branch.id, "name": branch.name, "city": branch.city,
        "phone": branch.phone, "waiting_now": waiting,
        "avg_wait_min": max(5, waiting * 8),
    })


@queue_bp.post("/register")
def register():
    data = request.get_json(force=True)
    required = ["branch_id", "full_name", "mobile", "service_type_id"]
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    # Validate inputs
    try:
        branch_id = int(data["branch_id"])
        service_type_id = int(data["service_type_id"])
    except (ValueError, TypeError):
        return jsonify({"error": "branch_id and service_type_id must be integers"}), 400
    
    full_name = str(data["full_name"]).strip()
    mobile = str(data["mobile"]).strip()
    
    if not full_name or len(full_name) < 2:
        return jsonify({"error": "Full name is required (min 2 characters)"}), 400
    
    if not mobile or len(mobile) < 9:
        return jsonify({"error": "Valid mobile number is required"}), 400

    try:
        priority_reason = PriorityReason[data.get("priority_reason", "NONE").upper()]
    except KeyError:
        priority_reason = PriorityReason.NONE
    is_priority = priority_reason != PriorityReason.NONE

    try:
        token = QueueService.register_customer(
            branch_id=branch_id,
            full_name=full_name,
            mobile=mobile,
            service_type_id=service_type_id,
            custom_reason=data.get("custom_reason"),
            is_priority=is_priority,
            priority_reason=priority_reason,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500

    position = QueueService.get_position(token)
    return jsonify({
        "token_id":       token.id,
        "token_number":   token.token_number,
        "service":        token.service_type.name,
        "service_code":   token.service_type.code,
        "position":       position,
        "estimated_wait": token.estimated_wait_min,
        "is_priority":    token.is_priority,
        "branch_name":    token.branch.name,
    }), 201


@queue_bp.get("/token/<int:token_id>/status")
def token_status(token_id):
    token = QueueToken.query.get_or_404(token_id)
    now_serving = (QueueToken.query
                   .filter_by(branch_id=token.branch_id,
                               service_type_id=token.service_type_id,
                               queue_date=date.today())
                   .filter(QueueToken.status.in_([TokenStatus.CALLED, TokenStatus.SERVING]))
                   .order_by(QueueToken.called_at.desc())
                   .first())
    return jsonify({
        "token_number": token.token_number,
        "status":       token.status.value,
        "position":     QueueService.get_position(token),
        "now_serving":  now_serving.token_number if now_serving else None,
        "counter":      token.counter.label if token.counter else None,
        "officer":      token.served_by_officer.full_name if token.served_by_officer else None,
        "called_at":    token.called_at.isoformat() if token.called_at else None,
    })


@queue_bp.post("/call-next")
@login_required
@require_role(UserRole.LOBBY_OFFICER, UserRole.LOAN_OFFICER, UserRole.BRANCH_MANAGER)
@audit_action("call_next")
def call_next():
    data       = request.get_json(force=True) or {}
    counter_id = data.get("counter_id")
    
    # Validate counter_id if provided
    if counter_id:
        try:
            counter_id = int(counter_id)
            counter = Counter.query.get(counter_id)
            if not counter or counter.branch_id != current_user.branch_id:
                return jsonify({"error": "Invalid counter"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "counter_id must be an integer"}), 400
    
    try:
        token = QueueService.call_next(current_user, counter_id)
        if not token:
            return jsonify({"message": "No customers waiting"}), 204
        return jsonify({
            "token_id":        token.id,
            "token_number":    token.token_number,
            "customer_name":   token.customer.full_name,
            "service":         token.service_type.name,
            "is_priority":     token.is_priority,
            "priority_reason": token.priority_reason.value,
            "counter":         token.counter.label if token.counter else None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@queue_bp.post("/token/<int:token_id>/start")
@login_required
@require_role(UserRole.LOBBY_OFFICER, UserRole.LOAN_OFFICER, UserRole.BRANCH_MANAGER)
@audit_action("start_service")
def start_service(token_id):
    token = QueueService.start_service(token_id, current_user)
    return jsonify({"message": "Service started", "token": token.token_number})


@queue_bp.post("/token/<int:token_id>/complete")
@login_required
@require_role(UserRole.LOBBY_OFFICER, UserRole.LOAN_OFFICER, UserRole.BRANCH_MANAGER)
@audit_action("complete_service")
def complete_service(token_id):
    token = QueueService.complete_service(token_id, current_user)
    return jsonify({"message": "Service completed", "token": token.token_number})


@queue_bp.post("/token/<int:token_id>/no-show")
@login_required
@require_role(UserRole.LOBBY_OFFICER, UserRole.LOAN_OFFICER, UserRole.BRANCH_MANAGER)
@audit_action("mark_no_show")
def mark_no_show(token_id):
    token = QueueService.mark_no_show(token_id)
    return jsonify({"message": "Marked as no-show", "token": token.token_number})


@queue_bp.post("/token/<int:token_id>/priority")
@login_required
@require_role(UserRole.LOBBY_OFFICER, UserRole.LOAN_OFFICER, UserRole.BRANCH_MANAGER)
@audit_action("upgrade_priority")
def upgrade_priority(token_id):
    data   = request.get_json(force=True) or {}
    reason = data.get("priority_reason", "ELDERLY").upper()
    
    # Validate priority reason
    try:
        priority_reason = PriorityReason[reason]
    except KeyError:
        return jsonify({"error": f"Invalid priority reason: {reason}. Must be one of: {', '.join([p.name for p in PriorityReason])}"}), 400
    
    try:
        token = QueueService.upgrade_priority(token_id, reason)
        return jsonify({"message": "Priority set", "token": token.token_number})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@queue_bp.post("/token/<int:token_id>/rate")
def rate_service(token_id):
    data       = request.get_json(force=True) or {}
    
    try:
        rating_val = int(data.get("rating", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "rating must be an integer"}), 400
    
    if not (1 <= rating_val <= 5):
        return jsonify({"error": "Rating must be between 1 and 5"}), 400
    
    token = QueueToken.query.get_or_404(token_id)
    if token.rating:
        return jsonify({"error": "Token already rated"}), 409
    
    try:
        r = SatisfactionRating(token_id=token_id, rating=rating_val,
                                comment=data.get("comment", ""))
        db.session.add(r)
        db.session.commit()
        return jsonify({"message": "Rating submitted. Thank you!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to submit rating: {str(e)}"}), 500


@queue_bp.get("/waiting")
@login_required
def get_waiting():
    service_ids = [s.id for s in ServiceType.query.filter(
        ServiceType.code.in_(current_user.allowed_service_codes)).all()]
    tokens = (QueueToken.query
              .filter_by(branch_id=current_user.branch_id,
                          status=TokenStatus.WAITING,
                          queue_date=date.today())
              .filter(QueueToken.service_type_id.in_(service_ids))
              .order_by(QueueToken.is_priority.desc(), QueueToken.id.asc())
              .all())
    return jsonify([{
        "id":              t.id,
        "token_number":    t.token_number,
        "customer_name":   t.customer.full_name,
        "service":         t.service_type.name,
        "service_code":    t.service_type.code,
        "is_priority":     t.is_priority,
        "priority_reason": t.priority_reason.value,
        "issued_at":       t.issued_at.isoformat(),
        "custom_reason":   t.custom_reason,
    } for t in tokens])


@queue_bp.get("/display/<string:branch_code>")
def display_state(branch_code):
    branch = Branch.query.filter_by(code=branch_code.upper(), is_active=True).first_or_404()
    today  = date.today()
    serving = (QueueToken.query
               .filter(QueueToken.branch_id == branch.id,
                       QueueToken.status.in_([TokenStatus.CALLED, TokenStatus.SERVING]),
                       QueueToken.queue_date == today)
               .order_by(QueueToken.called_at.desc())
               .all())
    waiting_next = (QueueToken.query
                    .filter_by(branch_id=branch.id,
                                status=TokenStatus.WAITING,
                                queue_date=today)
                    .order_by(QueueToken.is_priority.desc(), QueueToken.id.asc())
                    .limit(5).all())
    waiting_count = QueueToken.query.filter_by(
        branch_id=branch.id, status=TokenStatus.WAITING, queue_date=today).count()

    return jsonify({
        "branch":        branch.name,
        "waiting_count": waiting_count,
        "serving": [{
            "token":           t.token_number,
            "customer_name":   t.customer.full_name,
            "counter":         t.counter.label if t.counter else "",
            "service":         t.service_type.name,
            "service_code":    t.service_type.code,
            "is_priority":     t.is_priority,
            "priority_reason": t.priority_reason.value,
        } for t in serving],
        "next": [{
            "token":        t.token_number,
            "service":      t.service_type.name,
            "service_code": t.service_type.code,
        } for t in waiting_next],
    })
