import pandas as pd

FILE_PATH = r"D:\Data4DATN\Robust_With_Upgrade\HipsterShop_RCA_For_AI.csv"

def check_duplicate_traces():
    print(" Đang đọc file CSV và kiểm tra TraceID...\n")
    
    try:
        df = pd.read_csv(FILE_PATH)
        
        df.columns = [c.lower().strip() for c in df.columns]
        
        trace_col = next((c for c in df.columns if 'trace' in c), None)
        
        if not trace_col:
            print(f" Không tìm thấy cột nào chứa TraceID! Các cột hiện có: {df.columns.tolist()}")
            return

        print(f" Đã tìm thấy cột TraceID: '{trace_col}'")
        
        total_rows = len(df)
        unique_traces = df[trace_col].nunique()
        
        print("="*50)
        print(f" Tổng số dòng trong file : {total_rows:,}")
        print(f"Số TraceID DUY NHẤT    : {unique_traces:,}")
        
        duplicates = df[df.duplicated(subset=[trace_col], keep=False)]
        num_duplicates = len(duplicates)
        
        if total_rows > unique_traces:
            print(f"CẢNH BÁO: Phát hiện {total_rows - unique_traces:,} TraceID bị lặp lại (xuất hiện nhiều dòng chung 1 TraceID)!")
            print("="*50)
            print("\ Xem  5 dòng đầu tiên bị trùng lặp TraceID:")
            sample_dups = duplicates.sort_values(by=trace_col).head(5)
            print(sample_dups)
        else:
            print("Không có TraceID nào bị trùng lặp")
            print("="*50)

    except Exception as e:
        print(f" Lỗi khi đọc file: {e}")

if __name__ == "__main__":
    check_duplicate_traces()