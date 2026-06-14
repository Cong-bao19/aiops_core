from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session
import subprocess
import os
from datetime import datetime

from app.db.database import get_db
from app.services.mlops_service import get_training_data_logic

router = APIRouter(prefix="/api/v1/ai", tags=["MLOps & Model Lifecycle"])

AI_PROJECT_DIR = r"D:\Data4DATN\Robust_With_Upgrade"
CSV_TARGET_PATH = os.path.join(AI_PROJECT_DIR, "HipsterShop_RCA_For_AI - Copy.csv")

def run_full_mlops_pipeline(db: Session):
    """
    Luồng chạy ngầm: Xuất data -> Drain3 -> Embedding -> Train
    """
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [MLOPS] Bắt đầu MLOps Pipeline...")
    
    try:
       
        incident_count = get_training_data_logic(db, CSV_TARGET_PATH)
        
        if incident_count == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [MLOPS] Không có dữ liệu để Retrain.")
            return

        def run_script(script_name, step_name):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [MLOPS] ---> ĐANG CHẠY: {step_name}")
            PYTHON_AI = r"C:\Users\ADMIN\AppData\Local\Programs\Python\Python310\python.exe"

            process = subprocess.Popen(
    [PYTHON_AI, script_name],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding='cp1258',
    errors='ignore',
    cwd=AI_PROJECT_DIR
)
            for line in process.stdout:
                print(f"[{script_name}] {line.strip()}")
            process.wait()
            if process.returncode != 0:
                raise Exception(f"Script {script_name} thất bại!")

        run_script("run_drain3.py", "TIỀN XỬ LÝ DRAIN3")
        run_script("make_embedding.py", "TẠO EMBEDDING")
        run_script("train.py", "HUẤN LUYỆN MODEL")
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [MLOPS] 🎉 HOÀN TẤT RETRAIN!")

    except Exception as e:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [MLOPS] ❌ LỖI PIPELINE: {e}")

@router.post("/retrain")
async def trigger_model_retrain(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(run_full_mlops_pipeline, db)
    
    return {
        "status": "success",
        "message": "Hệ thống đã bắt đầu quá trình Retrain ngầm. Bạn có thể theo dõi log tại Backend console."
    }
#D:\Data4DATN\Robust_With_Upgrade\output\HipsterShop\session\train0.8_latest\reports\model_metadata.json
MODEL_METADATA_PATH = os.path.join(AI_PROJECT_DIR, r"output\HipsterShop\session\train0.8_latest\reports\model_metadata.json")
import json
@router.get("/evaluation")
async def get_model_evaluation():
    if os.path.exists(MODEL_METADATA_PATH):
        try:
            with open(MODEL_METADATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"Lỗi đọc file metadata: {e}")
            
    return {
        "model_name": "LogRobust (Bi-LSTM + Attention)",
        "version": "v1.0.0",
        "last_trained": "N/A (Chưa train)",
        "status": "AWAITING_TRAINING",
        "metrics": {
            "anomaly_recall": 0.0,     
            "healthy_accuracy": 0.0,   
            "root_cause_accuracy": 0.0,
            "f1_score": 0.0
        }
    }