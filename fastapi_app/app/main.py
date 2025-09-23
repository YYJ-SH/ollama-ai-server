import httpx
import base64
from fastapi import FastAPI, HTTPException, Header, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from . import config, database, models

app = FastAPI(
    title="Custom AI API Server with Qwen2.5-VL",
    description="A secure gateway to Ollama models with API key authentication + Qwen2.5-VL OCR endpoint."
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

# [기존] 사용 가능한 모델 리스트 API
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

# [기존] 메인 생성 API
@app.post("/v1/generate", tags=["Generation"])
async def generate_completion(
    request: models.OllamaRequest,
    api_key: dict = Depends(get_valid_api_key)
):
    # Ollama 고유 포맷으로 요청 본문 구성
    ollama_payload = {
        "model": request.model,
        "prompt": request.prompt,
        "stream": request.stream
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",  # ✅ 이 경로가 Ollama native API
                json=ollama_payload,
                timeout=180.0
            )
            response.raise_for_status()
            response_data = response.json()

            # ✅ 응답에서 텍스트 추출 후 DB 로그 기록
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


# ==================== 🔥 NEW: Qwen2.5-VL OCR 전용 엔드포인트 ====================

class QwenOCRRequest(BaseModel):
    """Qwen2.5-VL OCR 요청 모델"""
    image_base64: str
    prompt: Optional[str] = "이 이미지의 모든 텍스트를 정확히 읽어주세요. 한국어, 영어, 숫자를 모두 포함해서 줄바꿈도 유지해주세요."
    model: Optional[str] = "qwen2.5-vl:7b"
    temperature: Optional[float] = 0.1
    top_p: Optional[float] = 0.9

class QwenOCRResponse(BaseModel):
    """Qwen2.5-VL OCR 응답 모델"""
    success: bool
    ocr_text: str
    model_used: str
    processing_time_ms: float
    error: Optional[str] = None

@app.post("/v1/qwen/ocr", tags=["Qwen2.5-VL"], response_model=QwenOCRResponse)
async def qwen_ocr_endpoint(
    request: QwenOCRRequest,
    api_key: dict = Depends(get_valid_api_key)
):
    """
    Qwen2.5-VL을 사용한 고성능 OCR 엔드포인트
    
    - 한국어 최적화
    - Base64 이미지 입력
    - 빠른 응답 시간
    - 커스텀 프롬프트 지원
    """
    import time
    start_time = time.time()
    
    try:
        # Qwen2.5-VL 전용 페이로드 구성
        qwen_payload = {
            "model": request.model,
            "prompt": request.prompt,
            "images": [request.image_base64],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p
            }
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{config.OLLAMA_BASE_URL}/api/generate",
                    json=qwen_payload,
                    headers={'Content-Type': 'application/json'}
                )
                response.raise_for_status()
                result = response.json()
                
                processing_time = (time.time() - start_time) * 1000
                ocr_text = result.get("response", "").strip()
                
                if not ocr_text:
                    ocr_text = "[No text detected]"
                
                # DB 로그 기록 (선택사항)
                try:
                    await database.add_api_log(
                        owner=api_key.get("owner", "unknown"),
                        model=request.model,
                        prompt=f"[OCR] {request.prompt[:100]}...",
                        response=ocr_text[:500]  # OCR 결과는 길 수 있으니 500자만
                    )
                except Exception as log_e:
                    print(f"OCR 로그 기록 중 에러: {log_e}")
                
                return QwenOCRResponse(
                    success=True,
                    ocr_text=ocr_text,
                    model_used=request.model,
                    processing_time_ms=round(processing_time, 2),
                    error=None
                )
                
            except httpx.TimeoutException:
                return QwenOCRResponse(
                    success=False,
                    ocr_text="",
                    model_used=request.model,
                    processing_time_ms=round((time.time() - start_time) * 1000, 2),
                    error="OCR processing timeout (60s exceeded)"
                )
            except httpx.RequestError as e:
                return QwenOCRResponse(
                    success=False,
                    ocr_text="",
                    model_used=request.model,
                    processing_time_ms=round((time.time() - start_time) * 1000, 2),
                    error=f"Network error: {str(e)}"
                )
                
    except Exception as e:
        return QwenOCRResponse(
            success=False,
            ocr_text="",
            model_used=request.model,
            processing_time_ms=round((time.time() - start_time) * 1000, 2),
            error=f"Server error: {str(e)}"
        )

@app.post("/v1/qwen/ocr-file", tags=["Qwen2.5-VL"], response_model=QwenOCRResponse)
async def qwen_ocr_file_upload(
    file: UploadFile = File(..., description="이미지 파일 (PNG, JPG, JPEG)"),
    prompt: str = "이 이미지의 모든 텍스트를 정확히 읽어주세요. 한국어, 영어, 숫자를 모두 포함해서 줄바꿈도 유지해주세요.",
    model: str = "qwen2.5-vl:7b",
    temperature: float = 0.1,
    top_p: float = 0.9,
    api_key: dict = Depends(get_valid_api_key)
):
    """
    파일 업로드 방식의 Qwen2.5-VL OCR 엔드포인트
    """
    import time
    start_time = time.time()
    
    # 파일 타입 검증
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Only image files are supported")
    
    try:
        # 파일을 base64로 인코딩
        file_content = await file.read()
        image_base64 = base64.b64encode(file_content).decode('utf-8')
        
        # 기존 OCR 엔드포인트 재사용
        request_obj = QwenOCRRequest(
            image_base64=image_base64,
            prompt=prompt,
            model=model,
            temperature=temperature,
            top_p=top_p
        )
        
        # 내부적으로 qwen_ocr_endpoint 호출
        return await qwen_ocr_endpoint(request_obj, api_key)
        
    except Exception as e:
        return QwenOCRResponse(
            success=False,
            ocr_text="",
            model_used=model,
            processing_time_ms=round((time.time() - start_time) * 1000, 2),
            error=f"File processing error: {str(e)}"
        )

@app.get("/v1/qwen/health", tags=["Qwen2.5-VL"])
async def qwen_health_check(api_key: dict = Depends(get_valid_api_key)):
    """
    Qwen2.5-VL 모델 상태 확인
    """
    async with httpx.AsyncClient() as client:
        try:
            # 사용 가능한 모델 확인
            response = await client.get(f"{config.OLLAMA_BASE_URL}/api/tags")
            models_data = response.json()
            
            qwen_models = [
                model for model in models_data.get("models", [])
                if "qwen2.5-vl" in model.get("name", "").lower()
            ]
            
            return {
                "status": "healthy" if qwen_models else "no_qwen_models",
                "available_qwen_models": [m["name"] for m in qwen_models],
                "recommended_model": "qwen2.5-vl:7b",
                "endpoints": [
                    "/v1/qwen/ocr",
                    "/v1/qwen/ocr-file",
                    "/v1/qwen/health"
                ]
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Could not connect to Ollama server"
            }