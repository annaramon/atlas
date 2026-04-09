from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint
from app.models.base import Base


class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)
    sport_type = Column(String, nullable=False)
    source_file = Column(String, nullable=False, unique=True)

    total_duration = Column(Integer, nullable=True)   # seconds
    total_distance = Column(Float, nullable=True)     # meters
    total_ascent = Column(Float, nullable=True)       # meters
    calories = Column(Integer, nullable=True)

    hr_avg = Column(Integer, nullable=True)           # bpm
    hr_max = Column(Integer, nullable=True)           # bpm
    hr_min = Column(Integer, nullable=True)           # bpm

    hr_zone_1 = Column(Float, nullable=True)          # seconds in Z1
    hr_zone_2 = Column(Float, nullable=True)          # seconds in Z2
    hr_zone_3 = Column(Float, nullable=True)          # seconds in Z3
    hr_zone_4 = Column(Float, nullable=True)          # seconds in Z4
    hr_zone_5 = Column(Float, nullable=True)          # seconds in Z5
