import httpx
from fastapi import FastAPI, HTTPException, Header, Depends
from . import config, database, models

app = FastAPI(
    title="Custom AI API Server",
    description="A secure gateway to Ollama models with API key authentication."
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

# [신규] 사용 가능한 모델 리스트 API
@app.get("/v1/models", tags=["Models"])
async def list_available_models(api_key: dict = Depends(get_valid_api_key)):
    """
    Ollama 서버에 다운로드된 사용 가능한 모든 모델의 목록을 반환합니다.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{config.OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Could not connect to Ollama: {e}")

# 메인 생성 API
@app.post("/v1/generate", tags=["Generation"])
async def generate_completion(
    request: models.OllamaRequest,
    api_key: dict = Depends(get_valid_api_key)
):
    request_payload = request.model_dump()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",
                json=request_payload,
                timeout=180.0
            )
            response.raise_for_status()
            response_data = response.json()

            # --- 👇 [신규] 응답 성공 시 DB에 로그 기록 ---
            try:
                ai_response_text = response_data.get("response", "")
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
            raise HTTPException(status_code=500, detail=f"Error connecting to Ollama: {e}")
