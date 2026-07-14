from app.extensions import db
from datetime import datetime, timezone

class Customer(db.Model):
    __tablename__ = "customers"
    id         = db.Column(db.Integer, primary_key=True)
    full_name  = db.Column(db.String(120), nullable=False)
    mobile     = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    tokens = db.relationship("QueueToken", back_populates="customer", lazy="dynamic")
