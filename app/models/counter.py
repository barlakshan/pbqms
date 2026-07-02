from app.extensions import db

class Counter(db.Model):
    __tablename__ = "counters"
    id            = db.Column(db.Integer, primary_key=True)
    branch_id     = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=False)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"))
    label         = db.Column(db.String(20), nullable=False)
    service_scope = db.Column(db.String(20))
    is_active     = db.Column(db.Boolean, default=True)
    branch  = db.relationship("Branch", back_populates="counters")
    officer = db.relationship("User", foreign_keys=[user_id])
    tokens  = db.relationship("QueueToken", back_populates="counter", lazy="dynamic")
