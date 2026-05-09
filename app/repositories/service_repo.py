from sqlalchemy.orm import Session
from app.models.alert_model import Service

class ServiceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, name: str) -> Service:
        service = self.db.query(Service).filter(Service.name == name).first()
        if not service:
            service = Service(name=name)
            self.db.add(service)
            self.db.commit()
            self.db.refresh(service)
        return service