from sqlalchemy.orm import Session
from app.models.alert_model import Incident, IncidentStatusEnum, ErrorType
from app.repositories.errortype_repo import ErrorTypeRepository

class IncidentRepository:
    def __init__(self, db: Session):
        self.db = db
        self.error_type_repo = ErrorTypeRepository(db)
    
    def create_or_update_incident(self, service_id: int, title: str, diagnosis_code: int, diagnosis_name: str) -> int:
        if diagnosis_code == 0:
            return None
        error_type = self.error_type_repo.get_or_create_error_type(diagnosis_code, diagnosis_name)
        # Tìm lỗi cũ
        existing_incident = self.db.query(Incident).filter(
            Incident.service_id == service_id,
            Incident.error_type_id == error_type.id,
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
                error_type_id=error_type.id,
            )
            self.db.add(new_incident)
            self.db.commit()
            self.db.refresh(new_incident)
            return new_incident.id