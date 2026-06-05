import pandas as pd
from sqlalchemy import create_engine
from sklearn.metrics import classification_report, accuracy_score

GROUND_TRUTH_FILE = r"D:\Data4DATN\Robust_With_Upgrade\HipsterShop_RCA_For_AI.csv"
DB_URL = "postgresql://postgres:1234@localhost:5432/aiops_db" 

def evaluate_ai_predictions():
    print(" [BẮT ĐẦU] Đang đánh giá kết quả dự đoán của AI...")

    try:
        df_truth_raw = pd.read_csv(GROUND_TRUTH_FILE)
        df_truth_raw.columns = [c.lower().strip() for c in df_truth_raw.columns]
        
        trace_col = next((c for c in df_truth_raw.columns if 'trace' in c), None)
        label_col = next((c for c in df_truth_raw.columns if 'label' in c or 'class' in c), None)
        
        if not trace_col or not label_col:
            print(" Không tìm thấy cột TraceID hoặc Label!")
            return

        df_counts = df_truth_raw.groupby(trace_col).size().reset_index(name='so_dong_trung')
        df_truth = df_truth_raw.groupby(trace_col)[label_col].max().reset_index()
        df_truth = pd.merge(df_truth, df_counts, on=trace_col, how='left')
        
        print(f" Đã tải nhãn chuẩn: {len(df_truth):,} traces DUY NHẤT.")
    except Exception as e:
        print(f" Lỗi đọc file CSV: {e}")
        return

    try:
        engine = create_engine(DB_URL)
        query = """
            SELECT a.trace_id, e.code as diagnosis_code 
            FROM ai_predictions a
            JOIN error_types e ON a.error_type_id = e.id
        """
        df_pred_all = pd.read_sql(query, engine)
        
        if not df_pred_all.empty:
            df_pred = df_pred_all.groupby('trace_id')['diagnosis_code'].agg(lambda x: x.mode()[0]).reset_index()
        else:
            df_pred = pd.DataFrame(columns=['trace_id', 'diagnosis_code'])
            
        print(f" Đã tải dữ liệu dự đoán từ DB: {len(df_pred)} traces có lỗi.")
    except Exception as e:
        print(f" Lỗi kết nối Database: {e}")
        return

    df_merged = pd.merge(df_truth, df_pred, left_on=trace_col, right_on='trace_id', how='left')
    
    df_merged['diagnosis_code'] = df_merged['diagnosis_code'].fillna(0)
    df_merged['trace_id'] = df_merged[trace_col]

    print(f"Sẵn sàng đối chiếu {len(df_merged)} Traces.\n")
    
    print("\n" + "="*80)
    print(f"{'Trace ID':<35} | {'Label Gốc (CSV)':<15} | {'AI Dự Đoán (DB)'}")
    print("-" * 80)
    
    df_db_only = df_merged[df_merged['trace_id'].isin(df_pred['trace_id'])].copy()
    
    df_db_only = df_db_only.sort_values(by=label_col)
    
    for idx, row in df_db_only.iterrows():
        real_label = int(row[label_col])
        ai_pred = int(row['diagnosis_code'])
        
        status_icon = " ĐÚNG" if real_label == ai_pred else "SAI "
        print(f"{row['trace_id']:<35} | {real_label:<15} | {ai_pred} \t {status_icon}")
    
    print("="*80 + "\n")
    # =====================================================================

    y_true = df_merged[label_col].astype(int)
    y_pred = df_merged['diagnosis_code'].astype(int)

    acc = accuracy_score(y_true, y_pred)
    print("="*50)
    print(f"🏆 ĐỘ CHÍNH XÁC TỔNG THỂ (ACCURACY): {acc * 100:.2f}%")
    print("="*50)
    
    target_names = ['Class 0 (Normal)', 'Class 1 (Performance)', 'Class 2 (Exception)', 'Class 3 (Resource)']
    unique_classes = sorted(list(set(y_true) | set(y_pred)))
    labels = [target_names[i] for i in unique_classes]
    
    print(classification_report(y_true, y_pred, target_names=labels, zero_division=0))

if __name__ == "__main__":
    evaluate_ai_predictions()