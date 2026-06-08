from sqlalchemy.orm import Session
from app.models.alert_model import Incident

def get_training_data_logic(db: Session):
    """
    Lấy dữ liệu đã được con người (SRE/Ops) xác nhận nhãn (khác NULL)
    để tạo thành tập dữ liệu chuẩn bị Retrain AI.
    """
    verified_incidents = db.query(Incident).filter(
        Incident.human_error_type_id.isnot(None),
        Incident.status == "RESOLVED" 
    ).all()

    training_data = []
    
    for incident in verified_incidents:
        # Bỏ qua nhãn AI đoán sai (error_type_id)
        # Sử dụng nhãn chuẩn của con người (human_error_type_id)
        trace_ids = []
        if incident.recent_trace_ids:
            trace_ids = incident.recent_trace_ids.split(",")
            
        for trace_id in trace_ids:
            training_data.append({
                "trace_id": trace_id.strip(),
                "label_id": incident.human_error_type_id 
            })
        
    return training_data