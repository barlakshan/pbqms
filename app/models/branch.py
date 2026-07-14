from app.extensions import db
from datetime import datetime, timezone


class Branch(db.Model):
    __tablename__ = "branches"

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    code       = db.Column(db.String(10), unique=True, nullable=False)
    address    = db.Column(db.Text)
    city       = db.Column(db.String(80))
    phone      = db.Column(db.String(20))
    is_active  = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    users    = db.relationship("User",       back_populates="branch",   lazy="dynamic")
    counters = db.relationship("Counter",    back_populates="branch",   lazy="dynamic")
    tokens   = db.relationship("QueueToken", back_populates="branch",   lazy="dynamic")

    def qr_payload(self) -> str:
        try:
            from flask import current_app
            base = current_app.config.get("BASE_URL", "http://localhost:5000")
        except RuntimeError:
            base = "http://localhost:5000"
        return f"{base}/register/{self.code}"

    def __repr__(self):
        return f"<Branch {self.code}: {self.name}>"
