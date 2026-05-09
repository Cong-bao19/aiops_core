import httpx

AI_API_URL = "http://localhost:8000/stream_and_analyze"

async def analyze_log_with_ai(trace_id: str, raw_text: str) -> dict:
    async with httpx.AsyncClient() as client:
        payload = {"trace_id": trace_id, "raw_text": raw_text}
        
        # call port 8000  AI
        response = await client.post(AI_API_URL, json=payload, timeout=5.0)
        
        if response.status_code != 200:
            raise Exception("Lỗi kết nối tới AI Model")
            
        return response.json()