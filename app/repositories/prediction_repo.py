from sqlalchemy.orm import Session
from app.models.alert_model import AIPrediction

class PredictionRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_prediction(self, trace_id: str, service_id: int, incident_id: int, ai_result: dict, raw_text: str):
        new_prediction = AIPrediction(
            trace_id=trace_id,
            service_id=service_id,
            incident_id=incident_id,
            diagnosis_code=ai_result.get("diagnosis_code", 0),
            diagnosis_name=ai_result.get("diagnosis_name", "Normal"),
            confidence=ai_result.get("confidence_percent", 0.0),
            probabilities=ai_result.get("probabilities", {}),
            raw_log_context=raw_text,
            log_count=ai_result.get("current_log_count", 0)
        )
        self.db.add(new_prediction)
        self.db.commit()
        self.db.refresh(new_prediction)
        return new_prediction