from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.services.log_service import LogProcessingService
from app.schemas.alert_schema import LogIngestRequest, IngestResponse

import re
import json
from datetime import datetime
import httpx
from collections import defaultdict
import asyncio
import time

router = APIRouter(prefix="/api/v1/logs", tags=["Log Pipeline"])

# ==========================================
# 1. REGEX PRECOMPILE 
# ==========================================
PATTERN_PREFIX = re.compile(
    r'^\d{2}:\d{2}:\d{2}\.\d{3}\s+'
    r'(INFO|ERROR|WARN|DEBUG|WARNING|TRACE|FATAL)\s+-\s+'
)

PATTERN_BRACKET = re.compile(
    r'^\[[^\]]+\]\s+'
    r'(INFO|ERROR|WARN|DEBUG|WARNING|TRACE|FATAL)\s+'
)

PATTERN_TRACE = re.compile(
    r'TraceID:\s*([a-fA-F0-9-]+)',
    re.IGNORECASE
)

PATTERN_TRACE_REMOVE = re.compile(
    r'TraceID:\s*[a-fA-F0-9-]+\s*',
    re.IGNORECASE
)

PATTERN_SPAN = re.compile(
    r'SpanID:\s*[a-fA-F0-9-]+\s*',
    re.IGNORECASE
)

PATTERN_DASH = re.compile(r'^-\s+')


http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(
        connect=5.0,
        read=30.0,
        write=5.0,
        pool=5.0
    )
)

async def close_pipeline_resources():
    """Hàm gọi khi tắt Server để thu hồi tài nguyên HTTP an toàn"""
    await http_client.aclose()
    print(" [SHUTDOWN] Đã đóng các kết nối HTTP Client an toàn")


MAX_LOGS_PER_TRACE = 500

trace_buffers = defaultdict(
    lambda: {
        "service_name": "unknown",
        "logs": [],
        "start_time": time.time(),
        "last_updated": time.time()
    }
)

trace_locks = {}
_global_lock_manager = asyncio.Lock() 
async def get_trace_lock(trace_id: str):
    """Cấp phát Lock an toàn tuyệt đối cho từng Trace"""
    async with _global_lock_manager:
        if trace_id not in trace_locks:
            trace_locks[trace_id] = asyncio.Lock()
        return trace_locks[trace_id]


ai_task_queue = asyncio.Queue(maxsize=5000)


async def cleanup_expired_buffers():
    while True:
        await asyncio.sleep(30)
        now = time.time()

        expired_tids = [
            tid for tid, data in list(trace_buffers.items())
            if now - data["last_updated"] > 60
        ]

        for tid in expired_tids:
            lock = await get_trace_lock(tid)
            async with lock:
                if (tid in trace_buffers and now - trace_buffers[tid]["last_updated"] > 60):
                    trace_buffers.pop(tid, None)

            if tid not in trace_buffers:
                async with _global_lock_manager:
                    trace_locks.pop(tid, None)

# ==========================================
# AUTO FLUSH 
# ==========================================
async def auto_flush_buffers():
    while True:
        await asyncio.sleep(1)
        now = time.time()

        for tid, data in list(trace_buffers.items()):
            if not data["logs"]:
                continue

            if now - data["start_time"] < 5:
                continue

            should_put_queue = False
            batch_logs_to_send = []
            service_name = "unknown"

            lock = await get_trace_lock(tid)
            async with lock:
                if tid in trace_buffers and trace_buffers[tid]["logs"]:
                    should_put_queue = True
                    batch_logs_to_send = list(trace_buffers[tid]["logs"])
                    service_name = trace_buffers[tid]["service_name"]
                    
                    trace_buffers[tid]["logs"].clear()
                    trace_buffers[tid]["start_time"] = time.time()

            if should_put_queue:
                try:
                    if ai_task_queue.full():
                        try:
                            ai_task_queue.get_nowait()
                            ai_task_queue.task_done()
                        except:
                            pass

                    ai_task_queue.put_nowait({
                        "trace_id": tid,
                        "service_name": service_name,
                        "logs": batch_logs_to_send
                    })

                    print(f"⏰ [AUTO FLUSH] Trace {tid[:8]} | {len(batch_logs_to_send)} logs")

                except asyncio.QueueFull:
                    print(f"💥 Queue full when auto flush {tid[:8]}")

# ==========================================
# AI CONSUMERS 
# ==========================================
async def process_ai_queue_worker():
    while True:
        try:
            batch_data = await ai_task_queue.get()

            trace_id = batch_data["trace_id"]
            logs = batch_data["logs"]
            service_name = batch_data["service_name"]

            print(f" [WORKER] Processing {len(logs)} logs of Trace {trace_id[:8]}")

            success = False
            ai_result = None

            try:
                # Retry 3
                for attempt in range(3):
                    try:
                        response = await http_client.post(
                            "http://localhost:8000/batch_analyze",
                            json={
                                "trace_id": trace_id,
                                "logs": logs
                            }
                        )

                        if response.status_code == 200:
                            ai_result = response.json()
                            success = True
                            break

                    except httpx.RequestError:
                        await asyncio.sleep(1)

                # ==========================================
                # SAVE DATABASE 
                # ==========================================
                if (success and ai_result and ai_result.get("diagnosis_code", 0) != 0):
                    print(f" [AI DETECTED] Trace: {trace_id[:8]} | Code: {ai_result.get('diagnosis_code')}")

                    class MockRequest:
                        def __init__(self, t_id, s_name, r_text):
                            self.trace_id = t_id
                            self.service_name = s_name
                            self.raw_text = r_text

                    clean_request = MockRequest(
                        trace_id,
                        service_name,
                        logs[-1]["raw_text"]
                    )

                    db = SessionLocal()
                    try:
                        log_processor = LogProcessingService(db)
                        await asyncio.to_thread(
                            log_processor.process_and_save,
                            clean_request,
                            ai_result
                        )
                        print(f" [DB SAVED] Trace: {trace_id[:8]}")
                    except Exception as e:
                        print(f" [DB SAVE ERROR] {e}")
                        db.rollback()
                    finally:
                        db.close()

            except Exception as e:
                print(f" [WORKER ERROR] {e}")

            finally:
                ai_task_queue.task_done()
                if not success:
                    print(f" [DROP] Trace {trace_id[:8]}")

        except Exception as worker_crash:
            print(f" [WORKER CRASH] {worker_crash}")
            await asyncio.sleep(1)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_log(request: LogIngestRequest):
    try:
        raw_log = request.raw_text
        server_name = request.service_name
        actual_log_content = raw_log

        timestamp_str = request.timestamp if request.timestamp else datetime.now().isoformat()
        extracted_trace_id = server_name

        # --- BÓC TÁCH JSON ---
        try:
            outer_data = json.loads(raw_log)
            if not request.timestamp and "time" in outer_data:
                timestamp_str = outer_data["time"]

            if "log" in outer_data:
                inner_log_str = outer_data["log"].strip()
                try:
                    inner_data = json.loads(inner_log_str)
                    if "message" in inner_data:
                        actual_log_content = inner_data["message"]
                    if not request.timestamp and "timestamp" in inner_data:
                        timestamp_str = inner_data["timestamp"]
                except json.JSONDecodeError:
                    actual_log_content = inner_log_str
        except json.JSONDecodeError:
            pass

        trace_match = PATTERN_TRACE.search(actual_log_content)
        if trace_match:
            extracted_trace_id = trace_match.group(1)

        actual_log_content = PATTERN_PREFIX.sub('', actual_log_content)
        actual_log_content = PATTERN_BRACKET.sub('', actual_log_content)
        actual_log_content = PATTERN_TRACE_REMOVE.sub('', actual_log_content)
        actual_log_content = PATTERN_SPAN.sub('', actual_log_content).strip()
        actual_log_content = PATTERN_DASH.sub('', actual_log_content)

        if not actual_log_content:
            return IngestResponse(status="ignored", message="Log rỗng", is_anomaly=False)

        
        should_flush = False
        batch_logs_to_send = []

        lock = await get_trace_lock(extracted_trace_id)
        async with lock:
            trace_buffers[extracted_trace_id]["service_name"] = server_name
            
            trace_buffers[extracted_trace_id]["logs"].append({
                "raw_text": actual_log_content,
                "timestamp": timestamp_str
            })
            trace_buffers[extracted_trace_id]["last_updated"] = time.time()

            logs_count = len(trace_buffers[extracted_trace_id]["logs"])
            time_elapsed = time.time() - trace_buffers[extracted_trace_id]["start_time"]

            if logs_count >= 20 or time_elapsed >= 5 or logs_count >= MAX_LOGS_PER_TRACE:
                should_flush = True
                batch_logs_to_send = list(trace_buffers[extracted_trace_id]["logs"])
                
                trace_buffers[extracted_trace_id]["logs"].clear()
                trace_buffers[extracted_trace_id]["start_time"] = time.time()

        
        if should_flush:
            try:
                if ai_task_queue.full():
                    try:
                        ai_task_queue.get_nowait()
                        ai_task_queue.task_done()
                    except:
                        pass

                ai_task_queue.put_nowait({
                    "trace_id": extracted_trace_id,
                    "service_name": server_name,
                    "logs": batch_logs_to_send
                })

                print(f"📥 [QUEUED] {len(batch_logs_to_send)} logs of {extracted_trace_id[:8]}")

                return IngestResponse(
                    status="queued",
                    message="Đã đưa batch vào queue",
                    is_anomaly=False
                )

            except asyncio.QueueFull:
                return IngestResponse(
                    status="dropped",
                    message="Queue quá tải",
                    is_anomaly=False
                )

        return IngestResponse(
            status="buffering",
            message="Đang gom log...",
            is_anomaly=False
        )

    except Exception as e:
        print(f"[ERROR] API Ingest fail: {e}")
        raise HTTPException(status_code=500, detail=str(e))