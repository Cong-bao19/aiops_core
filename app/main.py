from fastapi import FastAPI
from app.controllers import log_controller
from fastapi.middleware.cors import CORSMiddleware
from app.controllers import pipeline_controller, incident_controller
import asyncio

app = FastAPI(title="AIOps Core API")


@app.on_event("startup")
async def startup_event():
    # 1. Khởi động máy dọn rác RAM & Auto Flush
    asyncio.create_task(pipeline_controller.cleanup_expired_buffers())
    asyncio.create_task(pipeline_controller.auto_flush_buffers())
    
    # 2. 🌟 FIX 3: SPAWN NHIỀU WORKER SONG SONG
    NUM_WORKERS = 5  # Tạo 5 công nhân gắp việc từ Queue
    for i in range(NUM_WORKERS):
        asyncio.create_task(pipeline_controller.process_ai_queue_worker())
        
    print(f"🚀 [STARTUP] Đã kích hoạt {NUM_WORKERS} AI Workers và các luồng dọn dẹp.")

# ==========================================
# TẮT HỆ THỐNG (SHUTDOWN)
# ==========================================
@app.on_event("shutdown")
async def shutdown_event():
    # 🌟 FIX 2: Đóng kết nối gọn gàng, chống tràn RAM và treo Socket
    print("⚠️ [SHUTDOWN] Đang dọn dẹp tài nguyên trước khi tắt server...")
    await pipeline_controller.close_pipeline_resources()
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # Cho phép nguồn từ cổng React
    allow_credentials=True,
    allow_methods=["*"],            # Cho phép tất cả các phương thức GET, POST, PUT, DELETE
    allow_headers=["*"],            # Cho phép tất cả các định dạng Header truyền lên
)
app.include_router(log_controller.router, prefix="/api/v1/logs", tags=["Logs Ingestion"])
app.include_router(pipeline_controller.router)
app.include_router(incident_controller.router)
@app.get("/")
def root():
    return {"message": "Hệ thống AIOps Backend đã sẵn sàng"}