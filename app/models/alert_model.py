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

class ErrorType(Base):
    __tablename__ = "error_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Integer, unique=True, index=True, nullable=False) # VD: 1, 2, 3
    name = Column(String(100), nullable=False)                      # VD: Normal, Performance...
    description = Column(String(255), nullable=True)                # Gợi ý cách fix

    incidents = relationship("Incident", back_populates="error_type")
    predictions = relationship("AIPrediction", back_populates="error_type")


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
    
    error_type_id = Column(Integer, ForeignKey("error_types.id"), nullable=False)
    title = Column(String(255), nullable=False)
    
    severity = Column(Enum(SeverityEnum), default=SeverityEnum.CRITICAL)
    status = Column(Enum(IncidentStatusEnum), default=IncidentStatusEnum.OPEN)
    
    occurrence_count = Column(Integer, default=1)
    recent_trace_ids = Column(String, nullable=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    service = relationship("Service", back_populates="incidents")
    error_type = relationship("ErrorType", back_populates="incidents")
    predictions = relationship("AIPrediction", back_populates="incident")


class AIPrediction(Base):
    __tablename__ = "ai_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String(100), index=True, nullable=False)
    
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True) 
    
    error_type_id = Column(Integer, ForeignKey("error_types.id"), nullable=False)
    confidence = Column(Float, nullable=False)
    
    probabilities = Column(JSONB, nullable=True)
    
    raw_log_context = Column(Text, nullable=True)
    log_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    service = relationship("Service", back_populates="predictions")
    incident = relationship("Incident", back_populates="predictions")
    error_type = relationship("ErrorType", back_populates="predictions")