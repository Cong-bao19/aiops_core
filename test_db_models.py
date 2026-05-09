from app.db.database import SessionLocal
from app.models.alert_model import Service, Incident, AIPrediction

def test_insert_data():
    # 1. Mở một phiên làm việc với Database
    db = SessionLocal()
    
    try:
        print("Đang thử thêm dữ liệu vào các bảng...")
        
        # 2. Thêm thử 1 Dịch vụ (Service)
        new_service = Service(
            name="frontend_test", 
            description="Service dùng để test model"
        )
        db.add(new_service)
        db.commit()
        db.refresh(new_service) # Lấy ID vừa được tự động sinh ra
        print(f" Đã tạo Service: {new_service.name} (ID: {new_service.id})")
        
        # 3. Thêm thử 1 Sự cố (Incident) nối với Service trên
        new_incident = Incident(
            service_id=new_service.id, # Dùng Khóa ngoại
            title="Lỗi thử nghiệm hệ thống",
            diagnosis_code=2,          # Giả sử là lỗi Exception
        )
        db.add(new_incident)
        db.commit()
        db.refresh(new_incident)
        print(f" Đã tạo Incident ID: {new_incident.id}")
        
        # 4. Thêm thử 1 Lịch sử dự đoán (AIPrediction)
        new_prediction = AIPrediction(
            trace_id="trace-test-001",
            service_id=new_service.id,
            incident_id=new_incident.id,
            diagnosis_code=2,
            diagnosis_name="Exception",
            confidence=99.9,
            probabilities={"Normal": 0.01, "Exception": 99.9}, # Thử lưu JSON
            raw_log_context="[ERROR] Test log  lỗi "
        )
        db.add(new_prediction)
        db.commit()
        print(f" Đã tạo AI Prediction (Trace: {new_prediction.trace_id})")
        
        print("\n MODEL DATABASE HOẠT ĐỘNG ")
        
    except Exception as e:
        print(f" Có lỗi xảy ra: {str(e)}")
        db.rollback() # Trả lại trạng thái cũ nếu lỗi
    finally:
        db.close() # Luôn nhớ đóng kết nối

if __name__ == "__main__":
    test_insert_data()