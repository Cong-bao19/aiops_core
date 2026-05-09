from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Optional, List
from datetime import datetime


class LogIngestRequest(BaseModel):
    trace_id: str = Field(..., description="Mã định danh luồng (Trace ID)")
    service_name: str = Field(..., description="Tên microservice (VD: frontend)")
    raw_text: str = Field(..., min_length=5, description="Nội dung chuỗi log thô")

class IngestResponse(BaseModel):
    status: str
    message: str
    is_anomaly: bool
    incident_id: Optional[int] = None


class IncidentDTOResponse(BaseModel):
    id: int
    title: str
    severity: str
    status: str
    occurrence_count: int
    first_seen: datetime
    last_seen: datetime
    
    
    model_config = ConfigDict(from_attributes=True) 

class AIPredictionDetailDTO(BaseModel):
    trace_id: str
    diagnosis_name: str
    confidence: float
    probabilities: Optional[Dict[str, float]] = None
    raw_log_context: str  
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class IncidentDetailResponse(IncidentDTOResponse):
    predictions: List[AIPredictionDetailDTO] = []
    
    model_config = ConfigDict(from_attributes=True)

class DashboardStatsResponse(BaseModel):
    total_incidents_today: int
    open_critical_incidents: int
    top_failing_service: Optional[str] = None