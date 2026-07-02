from flask import render_template, redirect, url_for, abort
from app.views import customer_bp
from app.models import Branch, ServiceType, QueueToken, TokenStatus
from datetime import date


@customer_bp.route("/register/<string:branch_code>")
def register(branch_code):
    branch = Branch.query.filter_by(code=branch_code.upper(), is_active=True).first_or_404()
    services = ServiceType.query.filter_by(is_active=True).order_by(ServiceType.id).all()
    waiting  = QueueToken.query.filter(
        QueueToken.branch_id == branch.id,
        QueueToken.queue_date == date.today(),
        QueueToken.status.in_([TokenStatus.WAITING, TokenStatus.CALLED, TokenStatus.SERVING]),
    ).count()
    avg_wait = max(5, waiting * 8)
    return render_template("customer/register.html",
                            branch=branch, services=services, avg_wait=avg_wait)


@customer_bp.route("/register/token/<int:token_id>")
def token_page(token_id):
    token = QueueToken.query.get_or_404(token_id)
    from app.services.queue_service import QueueService
    position  = QueueService.get_position(token)
    wait_pct  = max(5, 100 - int(position / 20 * 100)) if position else 95
    mobile    = token.customer.mobile
    masked    = mobile[:6] + "•" * max(0, len(mobile) - 6)
    return render_template("customer/token.html",
        token_id=token.id,
        token_number=token.token_number,
        service_name=token.service_type.name,
        branch_name=token.branch.name,
        mobile_masked=masked,
        position=position,
        estimated_wait=token.estimated_wait_min,
        is_priority=token.is_priority,
        priority_reason=token.priority_reason.value.title() if token.is_priority else "",
        wait_pct=wait_pct,
    )
