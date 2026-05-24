from sqlalchemy.orm import Session
from app.models.alert_model import AIPrediction,ErrorType
from app.repositories.errortype_repo import ErrorTypeRepository

class PredictionRepository:
    def __init__(self, db: Session):
        self.db = db
        self.error_type_repo = ErrorTypeRepository(db)

    def save_prediction(self, trace_id: str, service_id: int, incident_id: int, ai_result: dict, raw_text: str):
        diag_code = ai_result.get("diagnosis_code", 0)
        diag_name = ai_result.get("diagnosis_name", "Normal")
        
        error_type = self.error_type_repo.get_or_create_error_type(diag_code, diag_name)

        new_prediction = AIPrediction(
            trace_id=trace_id,
            service_id=service_id,
            incident_id=incident_id,
            error_type_id=error_type.id,
            confidence=ai_result.get("confidence_percent", 0.0),
            probabilities=ai_result.get("probabilities", {}),
            raw_log_context=raw_text,
            log_count=ai_result.get("current_log_count", 0)
        )
        self.db.add(new_prediction)
        self.db.commit()
        self.db.refresh(new_prediction)
        return new_prediction