from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import get_db
from app.schemas.alert_schema import IncidentDTOResponse
from app.models.alert_model import Incident, IncidentStatusEnum, AIPrediction, ErrorType
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.models.alert_model import Service
from app.schemas.alert_schema import ServiceDTO, ErrorTypeDTO

router = APIRouter(prefix="/api/v1/logs", tags=["Incident Dashboard"])

class StatusUpdateRequest(BaseModel):
    status: str
    resolution_note: Optional[str] = None

class BulkResolveRequest(BaseModel):
    incident_ids: List[int]

# ==========================================
# API: All INCIDENTS
# ==========================================
@router.get("/incidents", response_model=list[IncidentDTOResponse])
async def get_all_incidents(status: str = None, db: Session = Depends(get_db)):
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == IncidentStatusEnum(status))
    
    incidents = query.order_by(Incident.last_seen.desc()).all()
    
    result = []
    for inc in incidents:
        trace_ids = []
        if inc.recent_trace_ids:
            if isinstance(inc.recent_trace_ids, str):
                trace_ids = inc.recent_trace_ids.split(",")
            elif isinstance(inc.recent_trace_ids, list):
                trace_ids = [str(t) for t in inc.recent_trace_ids]
            
        result.append(IncidentDTOResponse(
            id=inc.id,
            title=inc.title,
            severity=inc.severity.value if hasattr(inc.severity, 'value') else inc.severity,
            status=inc.status.value if hasattr(inc.status, 'value') else inc.status,
            occurrence_count=inc.occurrence_count,
            first_seen=inc.first_seen,
            last_seen=inc.last_seen,
            service_name= inc.service.name if inc.service else "Unknown",
            error_type=inc.error_type
        ))
    return result

# ==========================================
# API: detail 1 INCIDENT 
# ==========================================
@router.get("/incidents/{incident_id}")
async def get_incident_detail(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Không tìm thấy Incident này!")
        
    trace_list = []
    if incident.recent_trace_ids:
        if isinstance(incident.recent_trace_ids, str):
            trace_list = incident.recent_trace_ids.split(",")
        elif isinstance(incident.recent_trace_ids, list):
            trace_list = [str(t) for t in incident.recent_trace_ids]

    return {
        "id": incident.id,
        "title": incident.title,
        "service_id": incident.service_id,
        "status": incident.status.value if hasattr(incident.status, 'value') else incident.status,
        "occurrence_count": incident.occurrence_count,
        "first_seen": incident.first_seen,
        "last_seen": incident.last_seen,
        "recent_traces": trace_list,
        "service_name": incident.service.name if incident.service else "Unknown",
        "error_type": {
            "id": incident.error_type.id,
            "code": incident.error_type.code,
            "name": incident.error_type.name,
            "description": incident.error_type.description
        } if incident.error_type else None
    }

# ==========================================
# API: detail LOG THEO TRACE ID
# ==========================================
@router.get("/traces/{trace_id}")
async def get_trace_details(trace_id: str, db: Session = Depends(get_db)):
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
# update status
# ==========================================
@router.put("/incidents/{incident_id}/status")
async def update_incident_status(incident_id: int, payload: StatusUpdateRequest, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự cố ")
    
    incident.status = payload.status
    incident.updated_at = datetime.now()
    
    if payload.status == "RESOLVED" and not incident.title.startswith("[RESOLVED]"):
        incident.title = f"[RESOLVED] {incident.title}"
    
    db.commit()
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