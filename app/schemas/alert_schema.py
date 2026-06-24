from pydantic import BaseModel, Field, ConfigDict, computed_field
from typing import Dict, Optional, List
from datetime import datetime


class LogIngestRequest(BaseModel):
    service_name: str = Field(..., description="Tên microservice (VD: frontend)")
    raw_text: str = Field(..., min_length=1, description="Nội dung chuỗi log thô")
    timestamp: Optional[str] = Field(
        default=None,
        description="Timestamp gốc từ client agent"
    )
class IngestResponse(BaseModel):
    status: str
    message: str
    is_anomaly: bool
    incident_id: Optional[int] = None

class ErrorTypeDTO(BaseModel):
    id: int
    code: int
    name: str
    description: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class IncidentDTOResponse(BaseModel):
    id: int
    title: str
    severity: str
    status: str
    occurrence_count: int
    first_seen: datetime
    last_seen: datetime
    service_name: Optional[str] = "Unknown"
    
    error_type: Optional[ErrorTypeDTO] = None
    notes: Optional[str] = None
    human_error_type: Optional[ErrorTypeDTO] = None

    @computed_field
    def is_human_verified(self) -> bool:
        return self.human_error_type is not None
    model_config = ConfigDict(from_attributes=True)

class AIPredictionDetailDTO(BaseModel):
    trace_id: str
    diagnosis_name: str
    confidence: float
    probabilities: Optional[Dict[str, float]] = None
    raw_log_context: str  
    created_at: datetime
    error_type: Optional[ErrorTypeDTO] = None
    model_config = ConfigDict(from_attributes=True)

class IncidentDetailResponse(IncidentDTOResponse):
    predictions: List[AIPredictionDetailDTO] = []
    
    model_config = ConfigDict(from_attributes=True)

class DashboardStatsResponse(BaseModel):
    total_incidents_today: int
    open_critical_incidents: int
    top_failing_service: Optional[str] = None

class ServiceDTO(BaseModel):
    id: int
    name: str
    
    model_config = ConfigDict(from_attributes=True)

class IncidentResolveRequest(BaseModel):
    actual_diagnosis_code: int  
    notes: str = ""            