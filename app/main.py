from fastapi import FastAPI
from app.controllers import log_controller

app = FastAPI(title="AIOps Core API")

app.include_router(log_controller.router, prefix="/api/v1/logs", tags=["Logs Ingestion"])

@app.get("/")
def root():
    return {"message": "Hệ thống AIOps Backend đã sẵn sàng"}