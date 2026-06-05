from app.db.database import SessionLocal
from app.models.alert_model import Service, Incident, AIPrediction

def test_insert_data():
    db = SessionLocal()
    
    try:
        print("Đang thử thêm dữ liệu vào các bảng...")
        
        new_service = Service(
            name="frontend_test", 
            description="Service dùng để test model"
        )
        db.add(new_service)
        db.commit()
        db.refresh(new_service) 
        print(f" Đã tạo Service: {new_service.name} (ID: {new_service.id})")
        
        new_incident = Incident(
            service_id=new_service.id, 
            title="Lỗi thử nghiệm hệ thống",
            diagnosis_code=2,         
        )
        db.add(new_incident)
        db.commit()
        db.refresh(new_incident)
        print(f" Đã tạo Incident ID: {new_incident.id}")
        
        new_prediction = AIPrediction(
            trace_id="trace-test-001",
            service_id=new_service.id,
            incident_id=new_incident.id,
            diagnosis_code=2,
            diagnosis_name="Exception",
            confidence=99.9,
            probabilities={"Normal": 0.01, "Exception": 99.9}, 
            raw_log_context="[ERROR] Test log  lỗi "
        )
        db.add(new_prediction)
        db.commit()
        print(f" Đã tạo AI Prediction (Trace: {new_prediction.trace_id})")
        
        print("\n MODEL DATABASE HOẠT ĐỘNG ")
        
    except Exception as e:
        print(f" Có lỗi xảy ra: {str(e)}")
        db.rollback()
    finally:
        db.close() 
if __name__ == "__main__":
    test_insert_data()