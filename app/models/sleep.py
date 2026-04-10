from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base


class Sleep(Base):
    __tablename__ = "sleep"

    id = Column(Integer, primary_key=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)
    sleep_id = Column(String, nullable=True)          # Suunto internal ID, used to join sleep_stages

    deep_duration = Column(Integer, nullable=True)    # seconds
    light_duration = Column(Integer, nullable=True)   # seconds
    rem_duration = Column(Integer, nullable=True)     # seconds

    hr_avg = Column(Integer, nullable=True)           # bpm (normalized from fraction on ingest)
    hr_min = Column(Integer, nullable=True)           # bpm (normalized from fraction on ingest)
    hrv = Column(Float, nullable=True)
    spo2_avg = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)

    stages = relationship("SleepStage", back_populates="sleep", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("recorded_at", name="uq_sleep_recorded_at"),)


class SleepStage(Base):
    __tablename__ = "sleep_stages"

    id = Column(Integer, primary_key=True)
    sleep_id = Column(Integer, ForeignKey("sleep.id"), nullable=False, index=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    stage = Column(String, nullable=False)            # deep / light / rem / awake
    duration = Column(Integer, nullable=False)        # seconds

    sleep = relationship("Sleep", back_populates="stages")

    __table_args__ = (UniqueConstraint("sleep_id", "recorded_at", name="uq_sleep_stage_sleep_id_recorded_at"),)
