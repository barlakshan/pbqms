from app.extensions import db
from datetime import datetime, date
import enum

class TokenStatus(enum.Enum):
    WAITING   = "waiting"
    CALLED    = "called"
    SERVING   = "serving"
    COMPLETED = "completed"
    NO_SHOW   = "no_show"
    SKIPPED   = "skipped"

class PriorityReason(enum.Enum):
    NONE     = "none"
    ELDERLY  = "elderly"
    PREGNANT = "pregnant"
    DISABLED = "disabled"

class QueueToken(db.Model):
    __tablename__ = "queue_tokens"
    id                 = db.Column(db.Integer, primary_key=True)
    branch_id          = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=False)
    customer_id        = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    service_type_id    = db.Column(db.Integer, db.ForeignKey("service_types.id"), nullable=False)
    counter_id         = db.Column(db.Integer, db.ForeignKey("counters.id"), nullable=True)
    served_by          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    token_number       = db.Column(db.String(10), nullable=False)
    custom_reason      = db.Column(db.Text, nullable=True)
    status             = db.Column(db.Enum(TokenStatus), default=TokenStatus.WAITING)
    is_priority        = db.Column(db.Boolean, default=False)
    priority_reason    = db.Column(db.Enum(PriorityReason), default=PriorityReason.NONE)
    estimated_wait_min = db.Column(db.Integer, default=0)
    issued_at          = db.Column(db.DateTime, default=datetime.utcnow)
    called_at          = db.Column(db.DateTime, nullable=True)
    served_at          = db.Column(db.DateTime, nullable=True)
    completed_at       = db.Column(db.DateTime, nullable=True)
    queue_date         = db.Column(db.Date, default=date.today)

    branch            = db.relationship("Branch", back_populates="tokens")
    customer          = db.relationship("Customer", back_populates="tokens")
    service_type      = db.relationship("ServiceType", back_populates="tokens")
    counter           = db.relationship("Counter", back_populates="tokens")
    served_by_officer = db.relationship("User", back_populates="tokens_served",
                                         foreign_keys=[served_by])
    sms_logs    = db.relationship("SmsLog", back_populates="token", lazy="dynamic")
    rating      = db.relationship("SatisfactionRating", back_populates="token", uselist=False)
    audit_logs  = db.relationship("AuditLog", back_populates="token", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("branch_id","service_type_id","token_number","queue_date",
                             name="uq_token_per_service_per_day"),
    )

    @property
    def actual_wait_minutes(self):
        if self.called_at and self.issued_at:
            return int((self.called_at - self.issued_at).total_seconds() / 60)
        return None

    @property
    def service_duration_minutes(self):
        if self.completed_at and self.served_at:
            return int((self.completed_at - self.served_at).total_seconds() / 60)
        return None
