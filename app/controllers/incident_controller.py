from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import get_db
from app.schemas.alert_schema import IncidentDTOResponse
from app.models.alert_model import Incident, IncidentStatusEnum, AIPrediction, ErrorType
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/api/v1/logs", tags=["Incident Dashboard"])

# Schema phụ vụ cập nhật trạng thái sự cố
class StatusUpdateRequest(BaseModel):
    status: str
    resolution_note: Optional[str] = None

class BulkResolveRequest(BaseModel):
    incident_ids: List[int]

# 1. API: LẤY TẤT CẢ INCIDENTS
@router.get("/incidents", response_model=list[IncidentDTOResponse])
async def get_all_incidents(status: str = None, db: Session = Depends(get_db)):
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == IncidentStatusEnum(status))
    
    incidents = query.order_by(Incident.last_seen.desc()).all()
    
    result = []
    for inc in incidents:
        result.append(IncidentDTOResponse(
            id=inc.id,
            title=inc.title,
            severity=inc.severity.value,
            status=inc.status.value,
            occurrence_count=inc.occurrence_count,
            first_seen=inc.first_seen,
            last_seen=inc.last_seen,
            error_type=inc.error_type
        ))
    return result

# 2. API: CHI TIẾT 1 INCIDENT
@router.get("/incidents/{incident_id}")
async def get_incident_detail(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Không tìm thấy Incident này!")
        
    trace_list = incident.recent_trace_ids.split(",") if incident.recent_trace_ids else []
    return {
        "id": incident.id,
        "title": incident.title,
        "service_id": incident.service_id,
        "status": incident.status,
        "occurrence_count": incident.occurrence_count,
        "first_seen": incident.first_seen,
        "last_seen": incident.last_seen,
        "recent_traces": trace_list,
        "error_type": {
            "id": incident.error_type.id,
            "code": incident.error_type.code,
            "name": incident.error_type.name,
            "description": incident.error_type.description
        } if incident.error_type else None
    }

# 3. API: CHI TIẾT LOG THEO TRACE ID
@router.get("/traces/{trace_id}")
async def get_trace_details(trace_id: str, db: Session = Depends(get_db)):
    trace_detail = db.query(AIPrediction).filter(AIPrediction.trace_id == trace_id).first()
    if not trace_detail:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu log chi tiết cho trace_id này!")
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

# 4. API NHÓM 1: CẬP NHẬT TRẠNG THÁI SỰ CỐ
@router.put("/incidents/{incident_id}/status")
async def update_incident_status(incident_id: int, payload: StatusUpdateRequest, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự cố này!")
    
    incident.status = payload.status
    incident.updated_at = datetime.now()
    
    if payload.status == "RESOLVED" and not incident.title.startswith("[RESOLVED]"):
        incident.title = f"[RESOLVED] {incident.title}"
    
    db.commit()
    return {"message": f"Sự cố #{incident_id} đã chuyển sang trạng thái {payload.status}"}

# 5. API NHÓM 2: THỐNG KÊ SỐ LIỆU ĐO LƯỜNG METRICS SUMMARY
@router.get("/metrics/summary")
async def get_aiops_metrics_summary(db: Session = Depends(get_db)):
    total_incidents = db.query(Incident).count()
    open_incidents = db.query(Incident).filter(Incident.status == IncidentStatusEnum.OPEN).count()
    investigating_incidents = db.query(Incident).filter(Incident.status == IncidentStatusEnum.ACKNOWLEDGED).count()
    
    resolved_incidents = db.query(Incident).filter(Incident.status == IncidentStatusEnum.RESOLVED).count()
    error_stats = db.query(AIPrediction.error_type_id, func.count(AIPrediction.id)).group_by(AIPrediction.error_type_id).all()
    
    distribution = {}
    for type_id, count in error_stats:
        if type_id is not None:
            err_type = db.query(ErrorType).filter(ErrorType.id == type_id).first()
            label = err_type.name if err_type else f"Mã nhãn {type_id}"
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