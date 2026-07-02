from app.extensions import db

class ServiceType(db.Model):
    __tablename__ = "service_types"
    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(5), unique=True, nullable=False)
    name            = db.Column(db.String(80), nullable=False)
    prefix          = db.Column(db.String(2), nullable=False)
    avg_service_min = db.Column(db.Integer, default=10)
    is_active       = db.Column(db.Boolean, default=True)
    tokens = db.relationship("QueueToken", back_populates="service_type", lazy="dynamic")
