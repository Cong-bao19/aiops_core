from sqlalchemy.orm import Session
from app.models.alert_model import Incident, IncidentStatusEnum

class IncidentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_or_update_incident(self, service_id: int, title: str, diagnosis_code: int) -> int:
        if diagnosis_code == 0:
            return None

        # Tìm lỗi cũ
        existing_incident = self.db.query(Incident).filter(
            Incident.service_id == service_id,
            Incident.diagnosis_code == diagnosis_code,
            Incident.status == IncidentStatusEnum.OPEN
        ).first()

        if existing_incident:
            existing_incident.occurrence_count += 1
            self.db.commit()
            return existing_incident.id
        else:
            # Tạo lỗi mới
            new_incident = Incident(
                service_id=service_id,
                title=title,
                diagnosis_code=diagnosis_code,
            )
            self.db.add(new_incident)
            self.db.commit()
            self.db.refresh(new_incident)
            return new_incident.id