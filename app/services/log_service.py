import hashlib
import re
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.alert_model import Incident, IncidentStatusEnum, Service, AIPrediction
from app.repositories.errortype_repo import ErrorTypeRepository

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
        template = re.sub(r'\d+', '', raw_text)
        template = re.sub(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '', template)
        return hashlib.md5(template.encode('utf-8')).hexdigest()[:8]

    def process_and_save(self, request, ai_result):
        diagnosis_code = ai_result.get("diagnosis_code", 0)
        diagnosis_name = ai_result.get("diagnosis_name", "Unknown Anomaly")
        
        if diagnosis_code == 0:
            return None

        error_type = self.error_type_repo.get_or_create_error_type(diagnosis_code, diagnosis_name)

        fingerprint = self._generate_fingerprint(request.raw_text)
        cache_key = f"{request.service_name}_{diagnosis_code}_{fingerprint}"
        
        now = datetime.now()

        if cache_key in LOCAL_ALERT_CACHE:
            cached_data = LOCAL_ALERT_CACHE[cache_key]
            
            if now < cached_data["expire_at"]:
                cached_data["count"] += 1
                
                if request.trace_id not in cached_data["recent_traces"]:
                    cached_data["recent_traces"].append(request.trace_id)
                    if len(cached_data["recent_traces"]) > 10:
                        cached_data["recent_traces"].pop(0)

                incident = self.db.query(Incident).filter(Incident.id == cached_data["incident_id"]).first()
                if incident:
                    incident.occurrence_count = cached_data["count"]
                    incident.last_seen = now
                    incident.recent_trace_ids = ",".join(cached_data["recent_traces"])
                
                new_prediction = AIPrediction(
                    trace_id=request.trace_id,
                    incident_id=cached_data["incident_id"],
                    error_type_id=error_type.id,
                    confidence=ai_result.get("confidence_percent", 0.0),
                    probabilities=ai_result.get("probabilities", {}),
                    raw_log_context=request.raw_text,
                    log_count=ai_result.get("current_log_count", 0)
                )
                self.db.add(new_prediction)
                self.db.commit()
                    
                return cached_data["incident_id"]
            else:
                del LOCAL_ALERT_CACHE[cache_key]

        safe_service_id = self.get_or_create_service_id(request.service_name)

        new_incident = Incident(
            service_id=safe_service_id,
            error_type_id=error_type.id,
            status=IncidentStatusEnum.OPEN,
            first_seen=now,
            last_seen=now,
            occurrence_count=1,
            title=f"[{fingerprint}] Phát hiện lỗi [{diagnosis_name}] bất thường", 
            recent_trace_ids=request.trace_id
        )
        self.db.add(new_incident)
        self.db.flush()

        new_prediction = AIPrediction(
            trace_id=request.trace_id,
            incident_id=new_incident.id,
            error_type_id=error_type.id,
            confidence=ai_result.get("confidence_percent", 0.0),
            probabilities=ai_result.get("probabilities", {}),
            raw_log_context=request.raw_text,
            log_count=ai_result.get("current_log_count", 0)
        )
        self.db.add(new_prediction)
        self.db.commit()
        self.db.refresh(new_incident)

        LOCAL_ALERT_CACHE[cache_key] = {
            "incident_id": new_incident.id,
            "count": 1,
            "recent_traces": [request.trace_id],
            "expire_at": now + timedelta(minutes=15)
        }
        return new_incident.id