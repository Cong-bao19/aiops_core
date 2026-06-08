from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from app.models.alert_model import Incident, IncidentStatusEnum, ErrorType
from app.schemas.alert_schema import IncidentDTOResponse
from datetime import datetime

def get_all_incidents_logic(db: Session, status: str = None):
    query = db.query(Incident).options(
        joinedload(Incident.error_type),
        joinedload(Incident.human_error_type),
        joinedload(Incident.service)
    )
    if status:
        query = query.filter(Incident.status == IncidentStatusEnum(status))
    
    incidents = query.order_by(Incident.last_seen.desc()).all()
    
    result = []
    for inc in incidents:
        dto = IncidentDTOResponse.model_validate(inc)
        dto.service_name = inc.service.name if inc.service else "Unknown" 
        result.append(dto)
        
    return result

def get_incident_detail_logic(db: Session, incident_id: int):
    incident = db.query(Incident).options(
        joinedload(Incident.error_type),
        joinedload(Incident.human_error_type),
        joinedload(Incident.service)
    ).filter(Incident.id == incident_id).first()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    trace_list = []
    if incident.recent_trace_ids:
        if isinstance(incident.recent_trace_ids, str):
            trace_list = incident.recent_trace_ids.split(",")
        elif isinstance(incident.recent_trace_ids, list):
            trace_list = [str(t) for t in incident.recent_trace_ids]
            
    incident_dict = IncidentDTOResponse.model_validate(incident).model_dump()
    incident_dict["recent_traces"] = trace_list
    incident_dict["service_name"] = incident.service.name if incident.service else "Unknown"
    incident_dict["status"] = incident.status.value if hasattr(incident.status, 'value') else incident.status
    
    return incident_dict

def update_incident_status_logic(db: Session, incident_id: int, status: str, resolution_note: str = None):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự cố")
    
    incident.status = status
    incident.updated_at = datetime.now()
    
    if status == "RESOLVED" and not incident.title.startswith("[RESOLVED]"):
        incident.title = f"[RESOLVED] {incident.title}"
        
    if resolution_note:
        incident.notes = resolution_note
    
    db.commit()
    return incident

def resolve_incident_logic(db: Session, incident_id: int, actual_diagnosis_code: int, notes: str):
    """
    Xử lý logic xác nhận sự cố và lưu nhãn chuẩn (Ground Truth) để Retrain AI.
    Đã fix lỗi lệch nhãn (Tìm ID thực sự từ bảng ErrorType thay vì lưu Code trực tiếp).
    """
    incident = db.query(Incident).options(
        joinedload(Incident.error_type),
        joinedload(Incident.human_error_type),
        joinedload(Incident.service)
    ).filter(Incident.id == incident_id).first()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự cố")

    # Lấy ID của loại lỗi thực sự dựa trên "Code" được truyền lên
    actual_error_type = db.query(ErrorType).filter(ErrorType.code == actual_diagnosis_code).first()
    
    if not actual_error_type:
        raise HTTPException(status_code=400, detail=f"Không tìm thấy loại lỗi có mã Code là {actual_diagnosis_code}")

    incident.status = "RESOLVED"
    incident.human_error_type_id = actual_error_type.id # Lưu ID thực tế, tránh râu ông nọ cắm cằm bà kia
    incident.notes = notes
    
    if not incident.title.startswith("[RESOLVED]"):
        incident.title = f"[RESOLVED] {incident.title}"
    
    db.commit()
    db.refresh(incident)
    
    dto = IncidentDTOResponse.model_validate(incident)
    dto.service_name = incident.service.name if incident.service else "Unknown"
    
    return dto