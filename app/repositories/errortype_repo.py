from sqlalchemy.orm import Session
from app.models.alert_model import ErrorType

class ErrorTypeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_error_type(self, code: int, name: str) -> ErrorType:
        error_type = self.db.query(ErrorType).filter(ErrorType.code == code).first()
        if not error_type:
            error_type = ErrorType(code=code, name=name)
            self.db.add(error_type)
            self.db.commit()
            self.db.refresh(error_type)
        return error_type