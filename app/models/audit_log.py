from app.extensions import db
from datetime import datetime, timezone

class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"))
    token_id   = db.Column(db.Integer, db.ForeignKey("queue_tokens.id"))
    action     = db.Column(db.String(80), nullable=False)
    payload    = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user  = db.relationship("User", back_populates="audit_logs")
    token = db.relationship("QueueToken", back_populates="audit_logs")
