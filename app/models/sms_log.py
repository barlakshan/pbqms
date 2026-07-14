from app.extensions import db
from datetime import datetime, timezone
import enum

class SmsType(enum.Enum):
    CONFIRMATION      = "confirmation"
    CALL_NOTIFICATION = "call_notification"

class SmsStatus(enum.Enum):
    PENDING = "pending"
    SENT    = "sent"
    FAILED  = "failed"

class SmsLog(db.Model):
    __tablename__ = "sms_logs"
    id                  = db.Column(db.Integer, primary_key=True)
    token_id            = db.Column(db.Integer, db.ForeignKey("queue_tokens.id"), nullable=False)
    sms_type            = db.Column(db.Enum(SmsType))
    mobile              = db.Column(db.String(20), nullable=False)
    message             = db.Column(db.Text, nullable=False)
    status              = db.Column(db.Enum(SmsStatus), default=SmsStatus.PENDING)
    provider_message_id = db.Column(db.String(80))
    sent_at             = db.Column(db.DateTime)
    created_at          = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    token = db.relationship("QueueToken", back_populates="sms_logs")
