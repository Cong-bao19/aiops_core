import httpx
import asyncio
import pandas as pd

LOG_FILE_PATH = r"D:\Data4DATN\Nezha\rca_data\2022-08-22\log\03_53_log.csv"
URL = "http://localhost:8080/api/v1/logs/ingest"

async def stream_realtime_logs():
    print(" [START] Client Agent đẩy log JSON thô về Backend...")

    try:
        df = pd.read_csv(LOG_FILE_PATH)

        if 'TimeUnixNano' in df.columns:
            df = df.sort_values(by='TimeUnixNano', ascending=True)
        else:
            df['Timestamp_Obj'] = pd.to_datetime(df['Timestamp'])
            df = df.sort_values(by='Timestamp_Obj', ascending=True)

        print(f" Đã đọc và sắp xếp thời gian thành công! Tổng số dòng: {len(df)}")

    except Exception as e:
        print(f" Lỗi khi đọc file CSV: {e}")
        return

    count = 0

    async with httpx.AsyncClient() as client:

        for index, row in df.iterrows():

            server_name = str(row.get('PodName', 'unknown_server'))
            raw_log_string = str(row.get('Log', ''))

            if not raw_log_string or str(raw_log_string) == 'nan':
                continue

            
            original_timestamp = None

            if 'TimeUnixNano' in row and pd.notna(row['TimeUnixNano']):
                original_timestamp = str(row['TimeUnixNano'])

            elif 'Timestamp' in row and pd.notna(row['Timestamp']):
                original_timestamp = str(row['Timestamp'])

            
            payload = {
                "service_name": server_name,
                "raw_text": raw_log_string,
                "timestamp": original_timestamp
            }

            try:
                count += 1

                response = await client.post(
                    URL,
                    json=payload,
                    timeout=5.0
                )

                res_data = response.json()

                if res_data.get('status') == "success":
                    print(
                        f" [Dòng {count:<4}] "
                        f"BE nhận log -> {res_data.get('message')}"
                    )

            except Exception:
                pass

            await asyncio.sleep(0.02)

    print(f"\n Đã quét xong {count} dòng hợp lệ và gửi về Backend!")

if __name__ == "__main__":
    asyncio.run(stream_realtime_logs())