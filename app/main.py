from fastapi import FastAPI
from app.controllers import log_controller
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="AIOps Core API")

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

@app.get("/")
def root():
    return {"message": "Hệ thống AIOps Backend đã sẵn sàng"}