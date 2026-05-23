from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.log_service import LogProcessingService
from app.schemas.alert_schema import LogIngestRequest, IngestResponse, IncidentDTOResponse
from app.models.alert_model import Incident, IncidentStatusEnum, AIPrediction
import re
import json
from datetime import datetime
import pandas as pd
import httpx
from collections import defaultdict
import time

router = APIRouter()
trace_buffers = defaultdict(lambda: {"logs": [], "start_time": time.time()})
async def analyze_log_with_ai(trace_id: str, raw_text: str, timestamp_str: str):
    AI_SERVER_URL = "http://localhost:8000/batch_analyze" 
    payload = {
        "trace_id": trace_id,
        "raw_text": raw_text,
        "timestamp": timestamp_str 
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(AI_SERVER_URL, json=payload, timeout=5.0)
            if response.status_code != 200:
                return None
            return response.json()
    except Exception as e:
        print(f"❌ Lỗi kết nối AI Server: {e}")
        return None

# =====================================================================
# 2. ENDPOINT TIẾP NHẬN LOG (BỘ LỌC RÁC ĐA TẦNG BULLETPROOF)
# =====================================================================
@router.post("/ingest", response_model=IngestResponse)
async def ingest_log(request: LogIngestRequest, db: Session = Depends(get_db)):
    try:
        raw_log = request.raw_text
        server_name = request.service_name
        actual_log_content = raw_log
        timestamp_str = request.timestamp if request.timestamp else datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        extracted_trace_id = server_name 
        
        # BƯỚC 1: BÓC TÁCH JSON
        try:
            outer_data = json.loads(raw_log)
            if not request.timestamp and "time" in outer_data: timestamp_str = outer_data["time"]
            if "log" in outer_data:
                inner_log_str = outer_data["log"].strip()
                try:
                    inner_data = json.loads(inner_log_str)
                    if "message" in inner_data: actual_log_content = inner_data["message"]
                    if not request.timestamp and "timestamp" in inner_data: timestamp_str = inner_data["timestamp"]
                except json.JSONDecodeError:
                    actual_log_content = inner_log_str
        except json.JSONDecodeError:
            pass

        # BƯỚC 2: MÓC TRACE_ID
        trace_match = re.search(r'TraceID:\s*([a-f0-9]+)', actual_log_content, re.IGNORECASE)
        if trace_match: extracted_trace_id = trace_match.group(1)

        # BƯỚC 3: XÓA RÁC
        actual_log_content = re.sub(r'^\d{2}:\d{2}:\d{2}\.\d{3}\s+(INFO|ERROR|WARN|DEBUG|WARNING|TRACE|FATAL)\s+-\s+', '', actual_log_content)
        actual_log_content = re.sub(r'^\[.*?\]\s+(INFO|ERROR|WARN|DEBUG|WARNING|TRACE|FATAL)\s+', '', actual_log_content)
        actual_log_content = re.sub(r'TraceID:\s*[a-f0-9-]+\s*', '', actual_log_content, flags=re.IGNORECASE)
        actual_log_content = re.sub(r'SpanID:\s*[a-f0-9-]+\s*', '', actual_log_content, flags=re.IGNORECASE)
        actual_log_content = actual_log_content.strip()
        actual_log_content = re.sub(r'^-\s+', '', actual_log_content)

        if not actual_log_content:
            return IngestResponse(status="ignored", message="Log rỗng", is_anomaly=False, incident_id=None)

        # BƯỚC 4: CHUẨN HÓA THỜI GIAN
        try:
            if re.fullmatch(r"\d+", str(timestamp_str)): dt_obj = pd.to_datetime(int(timestamp_str), unit='ns')
            else: dt_obj = pd.to_datetime(timestamp_str)
            normalized_timestamp = dt_obj.strftime("%Y-%m-%d %H:%M:%S,%f")
        except Exception:
            normalized_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")

        # -----------------------------------------------------------
        # BƯỚC 5: GOM LOG VÀO BUFFER (Gom theo TraceID)
        # -----------------------------------------------------------
        trace_buffers[extracted_trace_id]["logs"].append({
            "raw_text": actual_log_content,
            "timestamp": normalized_timestamp
        })
        
        logs_count = len(trace_buffers[extracted_trace_id]["logs"])
        time_elapsed = time.time() - trace_buffers[extracted_trace_id]["start_time"]
        
        # Log thông tin gom nhóm
        print(f"📦 [BUFFER] Trace: {extracted_trace_id[:8]} | Count: {logs_count}/20 | Time: {int(time_elapsed)}s")
        
        if logs_count >= 20 or time_elapsed >= 5:
            print(f"🚀 [FLUSH] Đang gửi batch {logs_count} log của Trace: {extracted_trace_id[:8]} sang AI...")
            
            batch_logs = trace_buffers[extracted_trace_id]["logs"]
            del trace_buffers[extracted_trace_id]
            last_response = None # <--- KHỞI TẠO Ở ĐÂY ĐỂ ĐẢM BẢO LUÔN TỒN TẠI
            log_processor = LogProcessingService(db)
            # 🌟 THAY VÌ LOOP, GỬI CẢ BATCH QUA AI
            async with httpx.AsyncClient() as client:
                # Gửi 1 request duy nhất chứa list logs
                payload = {"trace_id": extracted_trace_id, "logs": batch_logs}
                response = await client.post("http://localhost:8000/batch_analyze", json=payload, timeout=10.0)
                ai_result = response.json() if response.status_code == 200 else None

            # Nếu AI trả về kết quả dự đoán (Class != 0) thì lưu DB
            if ai_result:
                print(f"✅ [AI RESPONSE] Trace: {extracted_trace_id[:8]} | Mã lỗi: {ai_result.get('diagnosis_code')}")
                
                # Nếu AI dự đoán có lỗi (Class != 0) thì tiến hành lưu DB
                if ai_result.get("diagnosis_code", 0) != 0:
                    class MockRequest:
                        def __init__(self, t_id, s_name, r_text):
                            self.trace_id = t_id
                            self.service_name = s_name
                            self.raw_text = r_text
                    
                    last_log_in_batch = batch_logs[-1]
                    
                    # 🌟 ĐÃ SỬA: Đã nhét `server_name` vào giữa để đủ 3 tham số!
                    clean_request = MockRequest(extracted_trace_id, server_name, last_log_in_batch["raw_text"])
                    
                    last_response = log_processor.process_and_save(clean_request, ai_result)
                    print(f"💾 [DB SAVED] Đã lưu sự cố vào Database cho Trace: {extracted_trace_id[:8]}")
            else:
                print(f"⚠️ [AI WARNING] Không nhận được phản hồi từ AI cho Trace: {extracted_trace_id[:8]}")
            
            return IngestResponse(
                status="success", 
                message=f"Đã xử lý batch {logs_count} logs", 
                is_anomaly=False, 
                incident_id=last_response
            )

        return IngestResponse(
            status="buffering", 
            message=f"Đang gom log ({logs_count}/20 logs, {int(time_elapsed)}s)...",
            is_anomaly=False, 
            incident_id=None
        )

    except Exception as e:
        print(f"❌ [ERROR] Ingest fail: {e}")
        raise HTTPException(status_code=500, detail=str(e))
# =====================================================================
# 3. CÁC API THỐNG KÊ, DANH SÁCH INCIDENT (GIỮ NGUYÊN CODE CŨ CỦA BẠN)
# =====================================================================
"""@router.get("/stats", response_model=dict)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    log_processor = LogProcessingService(db)
    return log_processor.get_stats()"""

@router.get("/incidents", response_model=list[IncidentDTOResponse])
async def get_all_incidents(status: str = None, db: Session = Depends(get_db)):
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == IncidentStatusEnum(status))
    
    incidents = query.order_by(Incident.last_seen.desc()).all()
    
    result = []
    for inc in incidents:
        trace_list = inc.recent_trace_ids.split(",") if inc.recent_trace_ids else []
        result.append(IncidentDTOResponse(
            id=inc.id,
            title=inc.title,
            severity=inc.severity.value,
            status=inc.status.value,
            occurrence_count=inc.occurrence_count,
            first_seen=inc.first_seen,
            last_seen=inc.last_seen,
            # 🌟 ĐÃ SỬA: Map quan hệ sang ErrorTypeDTO tự động qua Pydantic từ ORM
            error_type=inc.error_type
        ))
    return result

@router.get("/incidents/{incident_id}")
async def get_incident_detail(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Không tìm thấy Incident này!")
        
    trace_list = incident.recent_trace_ids.split(",") if incident.recent_trace_ids else []
    return {
        "id": incident.id,
        "title": incident.title,
        "service_id": incident.service_id,
        "status": incident.status,
        "occurrence_count": incident.occurrence_count,
        "first_seen": incident.first_seen,
        "last_seen": incident.last_seen,
        "recent_traces": trace_list,
        # 🌟 ĐÃ SỬA: Thêm thông tin object ErrorType
        "error_type": {
            "id": incident.error_type.id,
            "code": incident.error_type.code,
            "name": incident.error_type.name,
            "description": incident.error_type.description
        } if incident.error_type else None
    }

from app.models.alert_model import AIPrediction

@router.get("/traces/{trace_id}")
async def get_trace_details(trace_id: str, db: Session = Depends(get_db)):
    trace_detail = db.query(AIPrediction).filter(AIPrediction.trace_id == trace_id).first()
    if not trace_detail:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu log chi tiết cho trace_id này!")
    return {
        "id": trace_detail.id,
        "trace_id": trace_detail.trace_id,
        "raw_log_context": trace_detail.raw_log_context, # Sửa lại đúng tên trường trong model mới
        "confidence_percent": trace_detail.confidence,    # Sửa lại đúng tên trường trong model mới
        "created_at": trace_detail.created_at,
        # 🌟 ĐÃ SỬA: Bóc dữ liệu từ bảng ErrorType thay vì trường thô cũ
        "error_type": {
            "id": trace_detail.error_type.id,
            "code": trace_detail.error_type.code,
            "name": trace_detail.error_type.name,
            "description": trace_detail.error_type.description
        } if trace_detail.error_type else None
    }