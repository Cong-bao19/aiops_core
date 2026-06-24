import asyncio
import httpx
import time
import pandas as pd
import ast
from tqdm.asyncio import tqdm_asyncio 

API_URL = "http://localhost:8080/api/v1/logs/ingest"
DATA_FILE_PATH = "test_readable.csv"

async def fire_request(client: httpx.AsyncClient, trace_id: str, raw_text: str, ground_truth_label: int):
    payload = {
        "trace_id": str(trace_id),
        "service_name": "frontend", 
        "raw_text": raw_text
    }
    try:
        response = await client.post(API_URL, json=payload, timeout=20.0)
        if response.status_code == 200:
            result = response.json()
            is_anomaly = result.get("is_anomaly", False)
            if ground_truth_label > 0 and is_anomaly: return True, "TP"
            elif ground_truth_label == 0 and not is_anomaly: return True, "TN"
            elif ground_truth_label == 0 and is_anomaly: return True, "FP"
            elif ground_truth_label > 0 and not is_anomaly: return True, "FN"
        return False, "ERROR"
    except:
        return False, "ERROR"

async def main():
    print(" Đang nạp data từ 'test_readable.csv' để chuẩn bị Bão cảnh báo...")
    try:
        df = pd.read_csv(DATA_FILE_PATH)
    except:
        print(" Lỗi đọc file data")
        return

    test_items = []
    
    error_row = df[df['Label'] > 0].iloc[0]
    raw_text = "\n".join(ast.literal_eval(error_row['Content']))
    label = error_row['Label']
    base_trace_id = error_row['SessionId']

    storm_size = 100 
    print(f" Đã tìm thấy 1 mẫu lỗi. Đang nhân bản lên {storm_size} lần...")
    
    for i in range(storm_size):
        test_items.append((f"{base_trace_id}_storm_{i}", raw_text, label))

    sem = asyncio.Semaphore(10) 
    async def bounded_fire_request(c, t, r, l):
        async with sem:
            return await fire_request(c, t, r, l)

    print(f"\n BẮT ĐẦU BẮN  {len(test_items)} LỖI GIỐNG NHAU VÀO BACKEND")
    start_time = time.time()

    async with httpx.AsyncClient() as client:
        tasks = [bounded_fire_request(client, trace_id, raw_text, label) for trace_id, raw_text, label in test_items]
        
        results = await tqdm_asyncio.gather(*tasks, desc=" Tiến độ ép tải")

    end_time = time.time()
    
    err = sum(1 for r, status in results if status == "ERROR")
    success_count = len(results) - err
    rps = len(test_items) / (end_time - start_time)

    print("\n" + "="*50)
    print(" KẾT QUẢ TEST BỘ NHỚ ĐỆM (RAM CACHE)")
    print("="*50)
    print(f" Tổng thời gian chạy: {end_time - start_time:.2f} giây")
    print(f" Tốc độ xử lý (RPS) : {rps:.2f} request/giây")
    print(f" Gửi thành công tới Backend: {success_count} / {storm_size}")
    print("-" * 50)
    print("BƯỚC TIẾP THEO: Hãy mở DB (bảng Incident) lên kiểm tra")
    print(f"Nếu Cache đúng, sẽ chỉ có 1 dòng Lỗi Frontend được tạo ra")
    print(f"với cột occurrence_count = {success_count}.")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())