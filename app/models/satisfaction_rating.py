from app.extensions import db
from datetime import datetime, timezone

class SatisfactionRating(db.Model):
    __tablename__ = "satisfaction_ratings"
    id       = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey("queue_tokens.id"),
                          nullable=False, unique=True)
    rating   = db.Column(db.Integer, nullable=False)
    comment  = db.Column(db.Text)
    rated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    token = db.relationship("QueueToken", back_populates="rating")
