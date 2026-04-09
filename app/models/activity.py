from sqlalchemy import Column, Integer, Float, DateTime, UniqueConstraint
from app.models.base import Base


class Activity(Base):
    __tablename__ = "activity"

    id = Column(Integer, primary_key=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)
    step_count = Column(Integer, nullable=True)
    energy_consumption = Column(Float, nullable=True)  # kcal

    __table_args__ = (UniqueConstraint("recorded_at", name="uq_activity_recorded_at"),)
