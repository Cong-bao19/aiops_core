from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session
import subprocess
import os
from datetime import datetime
from app.db.database import get_db
from app.services.mlops_service import get_training_data_logic

router = APIRouter(prefix="/api/v1/ai", tags=["MLOps & Model Lifecycle"])

AI_PROJECT_DIR = r"D:\Data4DATN\Robust_With_Upgrade"
CSV_TARGET_PATH = os.path.join(AI_PROJECT_DIR, r"HipsterShop_RCA_For_AI - Copy.csv")

LIVE_LOGS = []
IS_TRAINING = False

def push_log(msg: str):
    print(msg)
    LIVE_LOGS.append(msg)

def run_full_mlops_pipeline(db: Session):
    global IS_TRAINING
    try:
        push_log(f"[{datetime.now().strftime('%H:%M:%S')}] [MLOPS] MLOps Pipeline started...")
        incident_count = get_training_data_logic(db, CSV_TARGET_PATH)
        
        if incident_count == 0:
            push_log(f"[{datetime.now().strftime('%H:%M:%S')}] [MLOPS] No verified data found for retraining.")
            IS_TRAINING = False
            return

        def run_script(script_name, step_name):
            push_log(f"[{datetime.now().strftime('%H:%M:%S')}] [MLOPS] ---> RUNNING: {step_name}")
            
            process = subprocess.Popen(
                ["python", "-u", script_name], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                cwd=AI_PROJECT_DIR
            )
            
            for line_bytes in iter(process.stdout.readline, b''):
                line_str = line_bytes.decode('utf-8', errors='replace').strip()
                if line_str:
                    push_log(f"[{script_name}] {line_str}")
                    
            process.wait()
            if process.returncode != 0:
                raise Exception(f"Script {script_name} failed with exit code {process.returncode}")

        run_script("run_drain3.py", "DRAIN3 PREPROCESSING")
        run_script("make_embedding.py", "EMBEDDING GENERATION")
        run_script("train.py", "MODEL TRAINING")
        
        push_log(f"[{datetime.now().strftime('%H:%M:%S')}] [MLOPS]  PIPELINE SUCCESSFUL!")
    except Exception as e:
        push_log(f"[{datetime.now().strftime('%H:%M:%S')}] [MLOPS]  PIPELINE FAILED: {e}")
    finally:
        IS_TRAINING = False

@router.post("/retrain")
async def trigger_model_retrain(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    global IS_TRAINING, LIVE_LOGS
    if IS_TRAINING:
        return {"status": "warning", "message": "Pipeline is already running."}
    
    IS_TRAINING = True
    LIVE_LOGS.clear()
    
    background_tasks.add_task(run_full_mlops_pipeline, db)
    return {"status": "success", "message": "MLOps Pipeline triggered successfully."}

@router.get("/retrain-logs")
async def get_live_logs():
    return {
        "is_training": IS_TRAINING,
        "logs": LIVE_LOGS
    }

MODEL_METADATA_PATH = os.path.join(AI_PROJECT_DIR, r"output\HipsterShop\session\train0.8_latest\reports\model_metadata.json")
import json

@router.get("/evaluation")
async def get_model_evaluation():
    if os.path.exists(MODEL_METADATA_PATH):
        try:
            with open(MODEL_METADATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading metadata file: {e}")
            
    return {
        "model_name": "LogRobust (Bi-LSTM + Attention)",
        "version": "v1.0.0",
        "last_trained": "N/A",
        "status": "AWAITING_TRAINING",
        "metrics": {
            "anomaly_recall": 0.0,     
            "healthy_accuracy": 0.0,   
            "root_cause_accuracy": 0.0,
            "f1_score": 0.0
        }
    }