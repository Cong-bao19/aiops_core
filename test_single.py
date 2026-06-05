import httpx
import asyncio

async def test_realtime_stream():
    url = "http://localhost:8080/api/v1/logs/ingest"
    
    raw_logs_stream = [
        "[INFO]2023-08-20 01:50:46,584 data_integrate.py:481: [{'pod': 'frontend-579b9bff58-t2dbm', 'alarm': [{'metric_type': 'CpuUsageRate(%)', 'alarm_flag': True}]}]",
        "[INFO]2023-08-20 01:50:57,006 pattern_ranker.py:198: Soted Result List: [{'events': '76_4', 'score': 1.0, 'deepth': 1, 'pod': 'frontend-579b9bff58-t2dbm'}]",
        "[INFO]2023-08-20 01:50:57,088 pattern_ranker.py:553: 2022-08-22 03:53:10 Inject Ground Truth: frontend-579b9bff58-t2dbm, cpu_contention",
        "[INFO]2023-08-20 01:50:57,088 pattern_ranker.py:604: source :frontend hipstershop.Frontend/Recv. start, target: TraceID: <:TRACEID:> SpanID: <:SPANID:> Request started, pod frontend-579b9bff58-t2dbm",
        "[INFO]2023-08-20 01:51:27,312 pattern_ranker.py:607: source :TraceID: <:TRACEID:> SpanID: <:SPANID:> Serving product page started, target: TraceID: <:TRACEID:> SpanID: <:SPANID:> Choose Ad started, pod frontend-579b9bff58-t2dbm"
    ]

    async with httpx.AsyncClient() as client:
        print(" Khách hàng bắt đầu stream liên tục log thô về Backend...")
        
        for i, log_line in enumerate(raw_logs_stream, 1):
            payload = {
                "trace_id": "dynamic_client_stream",
                "service_name": "frontend-service",
                "raw_text": log_line
            }
            
            response = await client.post(url, json=payload, timeout=10.0)
            res_data = response.json()
            
            print(f"Dòng {i}/5 -> Trạng thái BE phản hồi: {res_data.get('status')} | Message: {res_data.get('message')}")
            
            await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(test_realtime_stream())