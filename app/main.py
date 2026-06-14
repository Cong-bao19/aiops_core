from fastapi import FastAPI
from app.controllers import log_controller
from fastapi.middleware.cors import CORSMiddleware
from app.controllers import pipeline_controller, incident_controller
import asyncio
import logging
from app.controllers import mlops_controller
class IgnoreUpgradeWarning(logging.Filter):
    def filter(self, record):
        return "Unsupported upgrade request" not in record.getMessage()

logging.getLogger("uvicorn.error").addFilter(IgnoreUpgradeWarning())
app = FastAPI(title="AIOps Core API")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(pipeline_controller.cleanup_expired_buffers())
    asyncio.create_task(pipeline_controller.auto_flush_buffers())
    
    NUM_WORKERS = 1  
    for i in range(NUM_WORKERS):
        asyncio.create_task(pipeline_controller.process_ai_queue_worker())
        
    print(f"s [STARTUP] Đã kích hoạt {NUM_WORKERS} AI Workers và các luồng dọn dẹp.")


@app.on_event("shutdown")
async def shutdown_event():
    print(" [SHUTDOWN] Đang dọn dẹp tài nguyên trước khi tắt server...")
    await pipeline_controller.close_pipeline_resources()
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          
    allow_credentials=True,
    allow_methods=["*"],            
    allow_headers=["*"],           
)
app.include_router(pipeline_controller.router)
app.include_router(incident_controller.router)
app.include_router(mlops_controller.router)
@app.get("/")
def root():
    return {"message": "Hệ thống AIOps Backend đã sẵn sàng"}