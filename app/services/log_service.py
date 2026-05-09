from sqlalchemy.orm import Session
from app.schemas.alert_schema import LogIngestRequest
from app.repositories.service_repo import ServiceRepository
from app.repositories.incident_repo import IncidentRepository
from app.repositories.prediction_repo import PredictionRepository

class LogProcessingService:
    def __init__(self, db: Session):
        # Khởi tạo  class Repository
        self.service_repo = ServiceRepository(db)
        self.incident_repo = IncidentRepository(db)
        self.prediction_repo = PredictionRepository(db)

    def process_and_save(self, request_data: LogIngestRequest, ai_result: dict) -> int:
        
        #  Service
        service = self.service_repo.get_or_create(request_data.service_name)
        
        #  Gom nhóm lỗi
        diagnosis_code = ai_result.get("diagnosis_code", 0)
        title = f"Cảnh báo: {ai_result.get('diagnosis_name')} tại {service.name}"
        
        incident_id = self.incident_repo.create_or_update_incident(
            service_id=service.id,
            title=title,
            diagnosis_code=diagnosis_code
        )
        
        #  Lưu  log thô
        self.prediction_repo.save_prediction(
            trace_id=request_data.trace_id,
            service_id=service.id,
            incident_id=incident_id,
            ai_result=ai_result,
            raw_text=request_data.raw_text
        )
        
        return incident_id