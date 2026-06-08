from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import get_db
from app.schemas.alert_schema import IncidentDTOResponse, ServiceDTO, ErrorTypeDTO, IncidentResolveRequest
from app.models.alert_model import Incident, IncidentStatusEnum, AIPrediction, ErrorType, Service
from pydantic import BaseModel
from typing import List, Optional

from app.services.incident_service import (
    get_all_incidents_logic,
    get_incident_detail_logic,
    update_incident_status_logic,
    resolve_incident_logic
)

router = APIRouter(prefix="/api/v1/logs", tags=["Incident Dashboard"])

class StatusUpdateRequest(BaseModel):
    status: str
    resolution_note: Optional[str] = None

class BulkResolveRequest(BaseModel):
    incident_ids: List[int]

# ==========================================
# API: ALL INCIDENTS
# ==========================================
@router.get("/incidents", response_model=list[IncidentDTOResponse])
async def get_all_incidents(status: str = None, db: Session = Depends(get_db)):
    # Đã bế khối logic cũ của bạn xuống service
    return get_all_incidents_logic(db=db, status=status)

# ==========================================
# API: DETAIL 1 INCIDENT 
# ==========================================
@router.get("/incidents/{incident_id}")
async def get_incident_detail(incident_id: int, db: Session = Depends(get_db)):
    return get_incident_detail_logic(db=db, incident_id=incident_id)

# ==========================================
# API: DETAIL LOG THEO TRACE ID
# ==========================================
@router.get("/traces/{trace_id}")
async def get_trace_details(trace_id: str, db: Session = Depends(get_db)):
    # Logic cũ của bạn giữ nguyên
    trace_detail = db.query(AIPrediction).filter(AIPrediction.trace_id == trace_id).first()
    if not trace_detail:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu log chi tiết cho trace_id")
    return {
        "id": trace_detail.id,
        "trace_id": trace_detail.trace_id,
        "raw_log_context": trace_detail.raw_log_context,
        "confidence_percent": trace_detail.confidence,
        "created_at": trace_detail.created_at,
        "error_type": {
            "id": trace_detail.error_type.id,
            "code": trace_detail.error_type.code,
            "name": trace_detail.error_type.name,
            "description": trace_detail.error_type.description
        } if trace_detail.error_type else None
    }

# ==========================================
# API: UPDATE STATUS
# ==========================================
@router.put("/incidents/{incident_id}/status")
async def update_incident_status(incident_id: int, payload: StatusUpdateRequest, db: Session = Depends(get_db)):
    update_incident_status_logic(
        db=db, 
        incident_id=incident_id, 
        status=payload.status, 
        resolution_note=payload.resolution_note
    )
    return {"message": f"Sự cố #{incident_id} đã chuyển sang trạng thái {payload.status}"}

# ==========================================
# SUMMARY
# ==========================================
@router.get("/metrics/summary")
async def get_aiops_metrics_summary(db: Session = Depends(get_db)):
    total_incidents = db.query(Incident).count()
    open_incidents = db.query(Incident).filter(Incident.status == IncidentStatusEnum.OPEN).count()
    investigating_incidents = db.query(Incident).filter(Incident.status == IncidentStatusEnum.ACKNOWLEDGED).count()
    
    resolved_incidents = db.query(Incident).filter(Incident.status == IncidentStatusEnum.RESOLVED).count()
    error_stats = db.query(
        AIPrediction.error_type_id,
        ErrorType.name,
        func.count(AIPrediction.id)
    ).outerjoin(ErrorType, AIPrediction.error_type_id == ErrorType.id)\
     .group_by(AIPrediction.error_type_id, ErrorType.name).all()
    
    distribution = {}
    for type_id, type_name, count in error_stats:
        if type_id is not None:
            label = type_name if type_name else f"Mã nhãn {type_id}"
            distribution[label] = count
        else:
            distribution["Chưa phân loại"] = count

    return {
        "summary": {
            "total": total_incidents,
            "open": open_incidents,
            "investigating": investigating_incidents,
            "resolved": resolved_incidents
        },
        "error_distribution": distribution if distribution else {"Hệ thống sạch (Normal)": 0}
    }

@router.get("/services", response_model=List[ServiceDTO])
async def get_all_services(db: Session = Depends(get_db)):
    return db.query(Service).order_by(Service.name.asc()).all()

@router.get("/error-types", response_model=List[ErrorTypeDTO])
async def get_all_error_types(db: Session = Depends(get_db)):
    return db.query(ErrorType).order_by(ErrorType.code.asc()).all()

# ==========================================
# API: RESOLVE VÀ LƯU NHÃN
# ==========================================
@router.put("/incidents/{incident_id}/resolve", response_model=IncidentDTOResponse)
def resolve_incident(   
    incident_id: int, 
    payload: IncidentResolveRequest, 
    db: Session = Depends(get_db)
):
    return resolve_incident_logic(
        db=db,
        incident_id=incident_id,
        actual_diagnosis_code=payload.actual_diagnosis_code,
        notes=payload.notes
    )