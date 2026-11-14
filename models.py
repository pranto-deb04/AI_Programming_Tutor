from sqlalchemy import Column, Integer, String, DateTime, Text
from database import Base
from datetime import datetime


class UserProfile(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, unique=True, index=True)
    name = Column(String)
    skill_level = Column(String, default="Beginner")


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, index=True)
    topic = Column(String)
    error_message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
