from sqlalchemy import Column, Integer, Float, DateTime, UniqueConstraint
from app.models.base import Base


class Recovery(Base):
    __tablename__ = "recovery"

    id = Column(Integer, primary_key=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)
    balance = Column(Float, nullable=True)             # 0–1
    stress_state = Column(Integer, nullable=True)

    __table_args__ = (UniqueConstraint("recorded_at", name="uq_recovery_recorded_at"),)
