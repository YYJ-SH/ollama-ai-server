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
    all_models = []
    all_model_names = set()

    async with httpx.AsyncClient() as client:
        for endpoint in set(config.OLLAMA_ENDPOINTS.values()):
            try:
                response = await client.get(f"{endpoint}/api/tags")
                response.raise_for_status()
                models_data = response.json()
                
                if "models" in models_data:
                    for model in models_data["models"]:
                        if model["name"] not in all_model_names:
                            all_models.append(model)
                            all_model_names.add(model["name"])

            except httpx.RequestError as e:
                # 개별 엔드포인트 실패는 무시하고 계속 진행
                print(f"Warning: Could not connect to Ollama at {endpoint}. Error: {e}")
                continue

    if not all_models:
        raise HTTPException(status_code=500, detail="Could not retrieve models from any Ollama server.")

    return {"models": all_models}

# [기존] 메인 생성 API
@app.post("/v1/generate", tags=["Generation"])
async def generate_completion(
    request: models.OllamaRequest,
    api_key: dict = Depends(get_valid_api_key)
):
    model_name = request.model.strip().lower()

    if model_name not in config.SUPPORTED_MODELS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 모델입니다: {model_name}")

    endpoint = config.OLLAMA_ENDPOINTS.get(model_name)
    if not endpoint:
        raise HTTPException(status_code=500, detail=f"모델 '{model_name}'에 대한 Ollama 엔드포인트를 찾을 수 없습니다.")

    ollama_payload = {
        "model": model_name,
        "prompt": request.prompt,
        "stream": request.stream,
        "options": request.options or {}
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{endpoint}/api/generate",
                json=ollama_payload,
                timeout=180.0
            )
            response.raise_for_status()
            response_data = response.json()

            # 로그 저장
            try:
                ai_response_text = response_data.get("response", "")
                await database.add_api_log(
                    owner=api_key.get("owner", "unknown"),
                    model=model_name,
                    prompt=request.prompt,
                    response=ai_response_text
                )
            except Exception as log_e:
                print(f"로그 기록 중 에러 발생: {log_e}")

            return response_data

        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Ollama 연결 오류: {e}")

# ==================== 🔥 NEW: Qwen2.5-VL OCR 전용 엔드포인트 ====================

class QwenOCRRequest(BaseModel):
    """Qwen2.5-VL OCR 요청 모델"""
    image_base64: str
    prompt: Optional[str] = "이 이미지의 모든 텍스트를 정확히 읽어주세요. 한국어, 영어, 숫자를 모두 포함해서 줄바꿈도 유지해주세요."
    model: Optional[str] = "qwen2.5vl:7b"
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
        
        endpoint = config.OLLAMA_ENDPOINTS.get(request.model)
        if not endpoint:
            raise HTTPException(status_code=500, detail=f"모델 '{request.model}'에 대한 Ollama 엔드포인트를 찾을 수 없습니다.")

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{endpoint}/api/generate",
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
                    error="OCR processing timeout (120s exceeded)"
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
    model: str = "qwen2.5vl:7b",
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
    qwen_models = []
    errors = []

    async with httpx.AsyncClient() as client:
        for endpoint in set(config.OLLAMA_ENDPOINTS.values()):
            try:
                response = await client.get(f"{endpoint}/api/tags")
                response.raise_for_status()
                models_data = response.json()
                
                for model in models_data.get("models", []):
                    if "qwen" in model.get("name", "").lower():
                        qwen_models.append(model["name"])

            except Exception as e:
                errors.append(f"Could not connect to {endpoint}: {str(e)}")
                continue

    if not qwen_models and errors:
        return {
            "status": "error",
            "errors": errors,
            "message": "Could not connect to any Ollama server or no Qwen models found."
        }

    return {
        "status": "healthy" if qwen_models else "no_qwen_models_found",
        "available_qwen_models": list(set(qwen_models)),
        "recommended_model": "qwen2.5vl:7b",
        "endpoints": [
            "/v1/qwen/ocr",
            "/v1/qwen/ocr-file",
            "/v1/qwen/health"
        ]
    }

# ==================== 🚀 NEW: PaddleOCR 엔드포인트 ====================
from paddleocr import PaddleOCR
import numpy as np
from PIL import Image
import io
import time

# PaddleOCR 인스턴스 초기화 (GPU 사용, 한국어+영어 모델)
# 서버 시작 시 한 번만 로드되도록 전역으로 선언
try:
    print("Initializing PaddleOCR...")
    paddle_ocr_instance = PaddleOCR(use_angle_cls=True, lang='korean', use_gpu=True)
    print("PaddleOCR initialized successfully.")
except Exception as e:
    print(f"Error initializing PaddleOCR: {e}")
    paddle_ocr_instance = None

class PaddleOCRResponse(BaseModel):
    success: bool
    results: Optional[List[dict]] = None
    processing_time_ms: float
    error: Optional[str] = None

@app.post("/v1/paddle/ocr", tags=["PaddleOCR"], response_model=PaddleOCRResponse)
async def paddle_ocr_endpoint(
    file: UploadFile = File(..., description="이미지 파일 (PNG, JPG, JPEG)"),
    api_key: dict = Depends(get_valid_api_key)
):
    """
    PaddleOCR을 사용한 고성능 OCR 엔드포인트

    - GPU 가속 지원 (서버 환경에 따라 설정)
    - 한국어, 영어, 숫자 등 다국어 인식
    - 이미지 파일을 직접 업로드하여 OCR 수행
    """
    if not paddle_ocr_instance:
        raise HTTPException(status_code=500, detail="PaddleOCR is not initialized. Check server logs for errors.")

    start_time = time.time()

    # 파일 타입 검증
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Only image files are supported")

    try:
        # 이미지 파일 읽기
        contents = await file.read()
        
        # Pillow를 사용하여 이미지 열기
        img = Image.open(io.BytesIO(contents))
        
        # 이미지를 numpy 배열로 변환
        img_np = np.array(img)

        # PaddleOCR 실행
        result = paddle_ocr_instance.ocr(img_np, cls=True)
        
        processing_time = (time.time() - start_time) * 1000

        # 결과 포맷팅
        formatted_results = []
        if result and result[0]:
            for line in result[0]:
                box = line[0]
                text, confidence = line[1]
                formatted_results.append({
                    "text": text,
                    "confidence": round(confidence, 4),
                    "box": {
                        "top_left": [int(p) for p in box[0]],
                        "top_right": [int(p) for p in box[1]],
                        "bottom_right": [int(p) for p in box[2]],
                        "bottom_left": [int(p) for p in box[3]],
                    }
                })

        return PaddleOCRResponse(
            success=True,
            results=formatted_results,
            processing_time_ms=round(processing_time, 2)
        )

    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        return PaddleOCRResponse(
            success=False,
            processing_time_ms=round(processing_time, 2),
            error=f"An error occurred during OCR processing: {str(e)}"
        )