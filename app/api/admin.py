from flask import request, jsonify
from flask_login import login_required
from app.api import admin_bp
from app.models import Branch, User, UserRole, AuditLog, Counter, ServiceType
from app.extensions import db
from app.utils.decorators import require_role, audit_action


@admin_bp.get("/branches")
@login_required
@require_role(UserRole.ADMIN)
def list_branches():
    branches = Branch.query.order_by(Branch.name).all()
    return jsonify([{
        "id": b.id, "name": b.name, "code": b.code,
        "city": b.city, "phone": b.phone, "is_active": b.is_active,
        "address": b.address,
    } for b in branches])


@admin_bp.post("/branches")
@login_required
@require_role(UserRole.ADMIN)
@audit_action("create_branch")
def create_branch():
    data = request.get_json(force=True)
    if not data.get("name") or not data.get("code"):
        return jsonify({"error": "Name and code are required"}), 400
    if Branch.query.filter_by(code=data["code"].upper()).first():
        return jsonify({"error": "Branch code already exists"}), 409
    branch = Branch(
        name=data["name"], code=data["code"].upper(),
        address=data.get("address"), city=data.get("city"), phone=data.get("phone"),
    )
    db.session.add(branch)
    db.session.commit()
    # Auto-create QR code
    try:
        from app.utils.qr_generator import generate_branch_qr
        generate_branch_qr(branch)
    except Exception:
        pass
    return jsonify({"id": branch.id, "code": branch.code, "name": branch.name}), 201


@admin_bp.put("/branches/<int:branch_id>")
@login_required
@require_role(UserRole.ADMIN)
@audit_action("update_branch")
def update_branch(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    data   = request.get_json(force=True)
    for f in ["name", "address", "city", "phone", "is_active"]:
        if f in data:
            setattr(branch, f, data[f])
    db.session.commit()
    return jsonify({"message": "Branch updated"})


@admin_bp.get("/branches/<int:branch_id>")
@login_required
@require_role(UserRole.ADMIN)
def get_branch(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    return jsonify({
        "id": branch.id,
        "name": branch.name,
        "code": branch.code,
        "address": branch.address,
        "city": branch.city,
        "phone": branch.phone,
        "is_active": branch.is_active,
    })


@admin_bp.delete("/branches/<int:branch_id>")
@login_required
@require_role(UserRole.ADMIN)
@audit_action("deactivate_branch")
def deactivate_branch(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    branch.is_active = False
    db.session.commit()
    return jsonify({"message": f"Branch {branch.name} deactivated"})


@admin_bp.get("/users")
@login_required
@require_role(UserRole.ADMIN)
def list_users():
    users = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    return jsonify([{
        "id": u.id, "employee_id": u.employee_id, "name": u.full_name,
        "email": u.email, "role": u.role.value,
        "branch_id": u.branch_id,
        "branch": u.branch.name if u.branch else None,
        "last_login": u.last_login.isoformat() if u.last_login else None,
    } for u in users])


@admin_bp.post("/users")
@login_required
@require_role(UserRole.ADMIN)
@audit_action("create_user")
def create_user():
    data = request.get_json(force=True)
    required = ["employee_id", "full_name", "email", "password", "role"]
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409
    try:
        role = UserRole[data["role"].upper()]
    except KeyError:
        return jsonify({"error": f"Invalid role: {data['role']}"}), 400
    u = User(
        employee_id=data["employee_id"], full_name=data["full_name"],
        email=data["email"].lower(), role=role,
        branch_id=data.get("branch_id"),
    )
    u.set_password(data["password"])
    db.session.add(u)
    db.session.commit()
    return jsonify({"id": u.id, "name": u.full_name}), 201


@admin_bp.put("/users/<int:user_id>")
@login_required
@require_role(UserRole.ADMIN)
@audit_action("update_user")
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json(force=True)
    for f in ["full_name", "email", "branch_id", "is_active"]:
        if f in data:
            setattr(user, f, data[f])
    if "role" in data:
        user.role = UserRole[data["role"].upper()]
    if "password" in data and data["password"]:
        user.set_password(data["password"])
    db.session.commit()
    return jsonify({"message": "User updated"})


@admin_bp.delete("/users/<int:user_id>")
@login_required
@require_role(UserRole.ADMIN)
@audit_action("deactivate_user")
def deactivate_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    return jsonify({"message": f"User {user.full_name} deactivated"})


@admin_bp.get("/audit-logs")
@login_required
@require_role(UserRole.ADMIN)
def audit_logs():
    page  = request.args.get("page", 1, type=int)
    per   = request.args.get("per_page", 50, type=int)
    logs  = (AuditLog.query
             .order_by(AuditLog.created_at.desc())
             .paginate(page=page, per_page=per, error_out=False))
    return jsonify({
        "items": [{
            "id":         l.id,
            "action":     l.action,
            "user":       l.user.full_name if l.user else "System",
            "ip":         l.ip_address,
            "payload":    l.payload,
            "created_at": l.created_at.isoformat(),
        } for l in logs.items],
        "total": logs.total, "pages": logs.pages, "page": page,
    })


@admin_bp.get("/qr/<int:branch_id>")
@login_required
@require_role(UserRole.ADMIN, UserRole.BRANCH_MANAGER)
def generate_qr_code(branch_id):
    """Generate QR code for a branch."""
    branch = Branch.query.get_or_404(branch_id)
    if current_user.role != UserRole.ADMIN and current_user.branch_id != branch.id:
        return jsonify({"error": "Access denied"}), 403
    try:
        from app.utils.qr_generator import generate_branch_qr
        qr_path = generate_branch_qr(branch)
        return jsonify({"qr_code_path": qr_path, "branch_code": branch.code}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.get("/customers")
@login_required
@require_role(UserRole.ADMIN)
def list_customers():
    from app.models import Customer, QueueToken
    from sqlalchemy import func
    page = request.args.get("page", 1, type=int)
    rows = (db.session.query(Customer, func.count(QueueToken.id).label("visits"))
            .outerjoin(QueueToken, QueueToken.customer_id == Customer.id)
            .group_by(Customer.id)
            .order_by(func.count(QueueToken.id).desc())
            .paginate(page=page, per_page=50, error_out=False))
    return jsonify({
        "items": [{
            "id":         c.id, "full_name": c.full_name,
            "mobile":     c.mobile, "visits": v,
            "registered": c.created_at.isoformat(),
        } for c, v in rows.items],
        "total": rows.total,
    })


@admin_bp.post("/qr/<int:branch_id>")
@login_required
@require_role(UserRole.ADMIN, UserRole.BRANCH_MANAGER)
def regen_qr(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    if current_user.role != UserRole.ADMIN and current_user.branch_id != branch.id:
        return jsonify({"error": "Access denied"}), 403
    from app.utils.qr_generator import generate_branch_qr
    path = generate_branch_qr(branch)
    return jsonify({"message": f"QR regenerated", "path": path})


@admin_bp.post("/counters")
@login_required
@require_role(UserRole.ADMIN, UserRole.BRANCH_MANAGER)
@audit_action("create_counter")
def create_counter():
    data = request.get_json(force=True)
    c = Counter(
        branch_id=data["branch_id"], label=data["label"],
        service_scope=data.get("service_scope"), user_id=data.get("user_id"),
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({"id": c.id, "label": c.label}), 201
