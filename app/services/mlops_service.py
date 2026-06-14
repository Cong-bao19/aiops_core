import pandas as pd
import json
import os
from sqlalchemy.orm import Session
from app.models.alert_model import Incident, AIPrediction

def get_training_data_logic(db: Session, output_csv_path: str):
    print("[MLOPS] Đang phục dựng CSV chuẩn từ DB...")
    
    verified_incidents = db.query(Incident).filter(
        Incident.human_error_type_id.isnot(None),
        Incident.status == "RESOLVED" 
    ).all()

    if not verified_incidents:
        return 0
        
    training_rows = []
    
    for incident in verified_incidents:
        trace_ids = [t.strip() for t in incident.recent_trace_ids.split(",")] if incident.recent_trace_ids else []
            
        for trace_id in trace_ids:
            prediction = db.query(AIPrediction).filter(AIPrediction.trace_id == trace_id).first()
            
            if prediction and prediction.raw_log_context:
                try:
                    data = json.loads(prediction.raw_log_context)
                    contents = data.get("contents", [])
                    time_deltas = data.get("time_deltas", [])
                    
                    for i in range(len(contents)):
                        t_delta = time_deltas[i] if i < len(time_deltas) else 0.0
                        
                        training_rows.append({
                            "Timestamp_Sec": 0.0,            # Giữ nguyên như file mẫu
                            "PodName": "unknown-pod",        
                            "TraceID": trace_id,
                            "Content": contents[i],
                            "Time_Delta": t_delta,
                            "Label": incident.human_error_type_id,
                            "EventId": 0,                    
                            "EventTemplate": ""             
                        })
                except Exception as e:
                    print(f"Lỗi parse JSON cho TraceID {trace_id}: {e}")

    if not training_rows:
        return 0

    
    import csv
    with open(output_csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["Timestamp_Sec", "PodName", "TraceID", "Content", "Time_Delta", "Label", "EventId", "EventTemplate"])
        writer.writeheader()
        for row in training_rows:
            row['Content'] = str(row['Content']).encode('ascii', 'ignore').decode('ascii')
            writer.writerow(row)
    
    print(f"[MLOPS] Đã xuất {len(training_rows)} dòng log sạch hoàn toàn ra: {output_csv_path}")
    return len(verified_incidents)