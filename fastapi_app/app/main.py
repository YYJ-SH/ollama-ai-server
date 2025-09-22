import httpx
from fastapi import FastAPI, HTTPException, Header, Depends
from . import config, database, models

app = FastAPI(
    title="Custom AI API Server (vLLM Edition)",
    description="A secure gateway to vLLM models with API key authentication."
)

# 서버 시작 시 DB 초기화
@app.on_event("startup")
def on_startup():
    database.init_db()

# API 키 검증을 위한 의존성 주입
async def get_valid_api_key(x_api_key: str = Header(..., description="Your personal API Key.")):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key is missing")
    key_info = await database.validate_and_log_key(x_api_key)
    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid or Inactive API Key")
    print(f"Request from '{key_info['owner']}' (Key: ...{x_api_key[-4:]})")
    return key_info

# [수정] vLLM의 모델 리스트 API
@app.get("/v1/models", tags=["Models"])
async def list_available_models(api_key: dict = Depends(get_valid_api_key)):
    """
    vLLM 서버에서 사용 가능한 모델의 목록을 반환합니다.
    """
    async with httpx.AsyncClient() as client:
        try:
            # vLLM의 OpenAI 호환 엔드포인트로 변경
            response = await client.get(f"{config.VLLM_BASE_URL}/v1/models")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Could not connect to vLLM: {e}")

# [수정] vLLM의 메인 생성 API
@app.post("/v1/generate", tags=["Generation"])
async def generate_completion(
    request: models.OllamaRequest,
    api_key: dict = Depends(get_valid_api_key)
):
    # vLLM은 OpenAI의 'messages' 배열 형식을 사용하므로 변환해줍니다.
    messages = [
        {"role": "user", "content": request.prompt}
    ]

    # vLLM에 보낼 최종 요청 본문(payload)
    vllm_payload = {
        "model": request.model,
        "messages": messages,
        "temperature": 0.7,
        "stream": request.stream
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # vLLM의 OpenAI 호환 엔드포인트로 변경
            response = await client.post(
                f"{config.VLLM_BASE_URL}/v1/chat/completions",
                json=vllm_payload,
                timeout=180.0
            )
            response.raise_for_status()
            response_data = response.json()

            # 응답 성공 시 DB에 로그 기록 (vLLM 응답 구조에 맞게 수정)
            try:
                # vLLM 응답에서 AI 답변 텍스트를 추출합니다.
                ai_response_text = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                await database.add_api_log(
                    owner=api_key.get("owner", "unknown"),
                    model=request.model,
                    prompt=request.prompt,
                    response=ai_response_text
                )
            except Exception as log_e:
                print(f"로그 기록 중 에러 발생: {log_e}")

            return response_data
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Error connecting to vLLM: {e}")