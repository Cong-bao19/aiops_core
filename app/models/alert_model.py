import enum
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class SeverityEnum(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class IncidentStatusEnum(str, enum.Enum):
    OPEN = "OPEN"                 # chờ xử lý
    ACKNOWLEDGED = "ACKNOWLEDGED" # đã tiếp nhận
    RESOLVED = "RESOLVED"         # xong


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    incidents = relationship("Incident", back_populates="service")
    predictions = relationship("AIPrediction", back_populates="service")

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    
    title = Column(String(255), nullable=False)
    diagnosis_code = Column(Integer, nullable=False) 
    
    severity = Column(Enum(SeverityEnum), default=SeverityEnum.CRITICAL)
    status = Column(Enum(IncidentStatusEnum), default=IncidentStatusEnum.OPEN)
    
    occurrence_count = Column(Integer, default=1)
    
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    service = relationship("Service", back_populates="incidents")
    predictions = relationship("AIPrediction", back_populates="incident")


class AIPrediction(Base):
    __tablename__ = "ai_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String(100), index=True, nullable=False)
    
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True) 
    
    diagnosis_code = Column(Integer, nullable=False)
    diagnosis_name = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    
    probabilities = Column(JSONB, nullable=True)
    
    raw_log_context = Column(Text, nullable=True)
    log_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    service = relationship("Service", back_populates="predictions")
    incident = relationship("Incident", back_populates="predictions")