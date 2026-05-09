from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.log_service import LogProcessingService
from app.schemas.alert_schema import LogIngestRequest, IngestResponse
from app.services.ai_service import analyze_log_with_ai
from app.schemas.alert_schema import LogIngestRequest, IngestResponse, IncidentDTOResponse, IncidentDetailResponse
from app.models.alert_model import Incident, IncidentStatusEnum
router = APIRouter()

@router.post("/ingest", response_model=IngestResponse)
async def ingest_log(request: LogIngestRequest, db: Session = Depends(get_db)):
    try:
        # call AI
        ai_result = await analyze_log_with_ai(request.trace_id, request.raw_text)

        # Service + Database 
        log_processor = LogProcessingService(db)
        incident_id = log_processor.process_and_save(request, ai_result)

        # result
        return IngestResponse(
            status="success",
            message="Đã phân tích và lưu vết thành công",
            is_anomaly=ai_result.get("diagnosis_code", 0) != 0,
            incident_id=incident_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats", response_model=dict)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """API lấy số liệu tổng quan cho các Thẻ (Card) trên cùng của Dashboard"""
    total_incidents = db.query(Incident).count()
    open_critical = db.query(Incident).filter(Incident.status == IncidentStatusEnum.OPEN).count()
    
    return {
        "total_incidents_today": total_incidents,
        "open_critical_incidents": open_critical,
        "top_failing_service": "frontend" 
    }
from typing import List
@router.get("/incidents", response_model=List[IncidentDTOResponse])
async def get_recent_incidents(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """API lấy danh sách Sự cố để vẽ lên Bảng (Table)"""
    incidents = db.query(Incident).order_by(Incident.last_seen.desc()).offset(skip).limit(limit).all()
    return incidents

@router.get("/incidents/{incident_id}/details", response_model=IncidentDetailResponse)
async def get_incident_details(incident_id: int, db: Session = Depends(get_db)):
    """API lấy chi tiết Sự cố + Bằng chứng Log thô"""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự cố này!")
        
    return incident