import hashlib
import re
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.alert_model import Incident, IncidentStatusEnum, Service, AIPrediction
from app.repositories.errortype_repo import ErrorTypeRepository
import json
LOCAL_ALERT_CACHE = {}
LOCAL_SERVICE_CACHE = {}

class LogProcessingService:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.error_type_repo = ErrorTypeRepository(db_session)

    def get_or_create_service_id(self, service_name: str) -> int:
        if service_name in LOCAL_SERVICE_CACHE:
            return LOCAL_SERVICE_CACHE[service_name]

        service = self.db.query(Service).filter(Service.name == service_name).first()
        if not service:
            try:
                new_service = Service(name=service_name)
                self.db.add(new_service)
                self.db.commit()
                self.db.refresh(new_service)
                service_id = new_service.id
            except IntegrityError:
                self.db.rollback()
                existing_service = self.db.query(Service).filter(Service.name == service_name).first()
                service_id = existing_service.id
        else:
            service_id = service.id

        LOCAL_SERVICE_CACHE[service_name] = service_id
        return service_id

    def _generate_fingerprint(self, raw_text: str) -> str:
        return hashlib.md5(raw_text.encode()).hexdigest()[:8]

    def process_and_save(self, payload: dict, ai_result: dict):
        trace_id = payload["trace_id"]
        service_name = payload["service_name"]
        raw_text = payload.get("raw_text", "")
        
        # =========================================================
        # 1. json pack
        # =========================================================
        contents = payload.get("contents", [])
        time_deltas = payload.get("time_deltas", [])
        
        if not contents:
            full_context = payload.get("full_context", raw_text)
            contents = [line.strip() for line in full_context.split('\n') if line.strip()]
            time_deltas = [0.0] * len(contents)
            
        context_to_save = json.dumps({
            "contents": contents,
            "time_deltas": time_deltas
        })

        diagnosis_code = ai_result.get("diagnosis_code", 0)
        diagnosis_name = ai_result.get("diagnosis_name", "Normal")

        log_clean = re.sub(r'\d+', '', raw_text)
        fingerprint = hashlib.md5(log_clean.encode('utf-8')).hexdigest()[:8]

        error_type = self.error_type_repo.get_or_create_error_type(diagnosis_code, diagnosis_name)
        now = datetime.now()

        existing_prediction = self.db.query(AIPrediction).filter(
            AIPrediction.trace_id == trace_id,
            AIPrediction.error_type_id == error_type.id
        ).first()

        if existing_prediction:
            existing_prediction.log_count = ai_result.get("current_log_count", 0)
            existing_prediction.confidence = ai_result.get("confidence_percent", 0.0)
            existing_prediction.probabilities = ai_result.get("probabilities", {})
            existing_prediction.raw_log_context = context_to_save
            
            incident = self.db.query(Incident).filter(Incident.id == existing_prediction.incident_id).first()
            if incident:
                incident.last_seen = now
                
            self.db.commit()
            return existing_prediction.incident_id

        else:
            safe_service_id = self.get_or_create_service_id(service_name)
            
            existing_incident = self.db.query(Incident).filter(
                Incident.service_id == safe_service_id,
                Incident.error_type_id == error_type.id,
                Incident.status == IncidentStatusEnum.OPEN
            ).first()

            if existing_incident:
                existing_incident.occurrence_count += 1
                existing_incident.last_seen = now
                
                recent_traces_list = existing_incident.recent_trace_ids.split(",") if existing_incident.recent_trace_ids else []
                if trace_id not in recent_traces_list:
                    recent_traces_list.append(trace_id)
                    existing_incident.recent_trace_ids = ",".join(recent_traces_list[-10:])
                
                self.db.flush()
                incident_id_to_use = existing_incident.id
                
            else:
                new_incident = Incident(
                    service_id=safe_service_id,
                    error_type_id=error_type.id,
                    status=IncidentStatusEnum.OPEN,
                    first_seen=now,
                    last_seen=now,
                    occurrence_count=1,
                    title=f"[{fingerprint}] Detected [{diagnosis_name}] anomaly",
                    recent_trace_ids=trace_id
                )
                self.db.add(new_incident)
                self.db.flush() 
                incident_id_to_use = new_incident.id

            new_prediction = AIPrediction(
                trace_id=trace_id,
                incident_id=incident_id_to_use,
                service_id=safe_service_id,  
                error_type_id=error_type.id,
                confidence=ai_result.get("confidence_percent", 0.0),
                probabilities=ai_result.get("probabilities", {}),
                raw_log_context=context_to_save,  
                log_count=ai_result.get("current_log_count", 0)
            )
            self.db.add(new_prediction)
            self.db.commit()
            return incident_id_to_use

def resolve_incident_logic(db: Session, incident_id: int, actual_diagnosis_code: int, notes: str):
    """
    Service: Xử lý logic xác nhận sự cố và lưu nhãn chuẩn (Ground Truth).
    """
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự cố")

    incident.status = "RESOLVED"
    incident.human_diagnosis_code = actual_diagnosis_code
    incident.notes = notes
    
    db.commit()
    db.refresh(incident)
    
    return incident