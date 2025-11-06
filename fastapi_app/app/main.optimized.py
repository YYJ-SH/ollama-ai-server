import httpx
import base64
from fastapi import FastAPI, HTTPException, Header, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from . import config, database, models

app = FastAPI(
    title="Optimized AI API Server (Qwen2.5-VL + GPT-OSS)",
    description="고성능 2-GPU 전용 서버: Qwen2.5-VL (OCR) + GPT-OSS (분석)"
)

# 🔥 서버 시작 시 모델 미리 로드 (Warm-up)
@app.on_event("startup")
async def on_startup():
    database.init_db()
    
    # 🔥 모델 워밍업: 서버 시작 시 두 모델 모두 미리 로드
    print("🚀 모델 워밍업 시작...")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # GPU 0: Qwen2.5-VL 워밍업
            print("  ↳ GPU 0: qwen2.5vl:7b 로딩중...")
            await client.post(
                "http://ollama_gpu0:11434/api/generate",
                json={
                    "model": "qwen2.5vl:7b",
                    "prompt": "warmup",
                    "stream": False,
                    "keep_alive": -1  # 🔥 영구 유지
                }
            )
            print("  ✅ GPU 0: qwen2.5vl:7b 로드 완료")
            
            # GPU 1: GPT-OSS 워밍업
            print("  ↳ GPU 1: gpt-oss:20b 로딩중...")
            await client.post(
                "http://ollama_gpu1:11434/api/generate",
                json={
                    "model": "gpt-oss:20b",
                    "prompt": "warmup",
                    "stream": False,
                    "keep_alive": -1  # 🔥 영구 유지
                }
            )
            print("  ✅ GPU 1: gpt-oss:20b 로드 완료")
            print("🎉 모든 모델 워밍업 완료!")
            
        except Exception as e:
            print(f"⚠️ 워밍업 중 에러 (무시됨): {e}")

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
    고정된 2개 모델 반환 (모델 스왑 없음)
    """
    return {
        "models": [
            {
                "name": "qwen2.5vl:7b",
                "gpu": "GPU 0 (RTX 3060)",
                "purpose": "OCR, 이미지 분석",
                "size": "7B",
                "endpoint": config.OLLAMA_ENDPOINTS["qwen2.5vl:7b"]
            },
            {
                "name": "gpt-oss:20b",
                "gpu": "GPU 1 (RTX 5060 Ti)",
                "purpose": "상세 분석, 추론",
                "size": "20B",
                "endpoint": config.OLLAMA_ENDPOINTS["gpt-oss:20b"]
            }
        ]
    }

# [기존] 메인 생성 API (타임아웃 증가)
@app.post("/v1/generate", tags=["Generation"])
async def generate_completion(
    request: models.OllamaRequest,
    api_key: dict = Depends(get_valid_api_key)
):
    model_name = request.model.strip().lower()

    if model_name not in config.SUPPORTED_MODELS:
        raise HTTPException(
            status_code=400, 
            detail=f"지원하지 않는 모델입니다. 사용 가능: {list(config.SUPPORTED_MODELS)}"
        )

    endpoint = config.OLLAMA_ENDPOINTS.get(model_name)
    if not endpoint:
        raise HTTPException(status_code=500, detail=f"모델 '{model_name}'에 대한 엔드포인트를 찾을 수 없습니다.")

    ollama_payload = {
        "model": model_name,
        "prompt": request.prompt,
        "stream": request.stream,
        "options": request.options or {},
        "keep_alive": -1  # 🔥 모델을 메모리에 유지
    }

    async with httpx.AsyncClient(timeout=config.OLLAMA_REQUEST_TIMEOUT) as client:
        try:
            response = await client.post(
                f"{endpoint}/api/generate",
                json=ollama_payload
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

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504, 
                detail=f"요청 타임아웃 ({config.OLLAMA_REQUEST_TIMEOUT}초 초과)"
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Ollama 연결 오류: {e}")

# ==================== 🔥 최적화된 Qwen2.5-VL OCR 엔드포인트 ====================

class QwenOCRRequest(BaseModel):
    """Qwen2.5-VL OCR 요청 모델"""
    image_base64: str
    prompt: Optional[str] = "이 이미지의 모든 텍스트를 정확히 읽어주세요. 한국어, 영어, 숫자를 모두 포함해서 줄바꿈도 유지해주세요."
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
    🚀 최적화된 Qwen2.5-VL OCR 엔드포인트
    
    - 모델 고정 (qwen2.5vl:7b only)
    - 타임아웃 300초
    - 모델 영구 메모리 유지
    """
    import time
    start_time = time.time()

    try:
        # 🔥 모델 고정
        model = "qwen2.5vl:7b"
        
        # Qwen2.5-VL 전용 페이로드 구성
        qwen_payload = {
            "model": model,
            "prompt": request.prompt,
            "images": [request.image_base64],
            "stream": False,
            "keep_alive": -1,  # 🔥 모델 유지
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p
            }
        }

        endpoint = config.OLLAMA_ENDPOINTS[model]

        async with httpx.AsyncClient(timeout=config.OLLAMA_REQUEST_TIMEOUT) as client:
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

                # DB 로그 기록
                try:
                    await database.add_api_log(
                        owner=api_key.get("owner", "unknown"),
                        model=model,
                        prompt=f"[OCR] {request.prompt[:100]}...",
                        response=ocr_text[:500]
                    )
                except Exception as log_e:
                    print(f"OCR 로그 기록 중 에러: {log_e}")

                return QwenOCRResponse(
                    success=True,
                    ocr_text=ocr_text,
                    model_used=model,
                    processing_time_ms=round(processing_time, 2),
                    error=None
                )

            except httpx.TimeoutException:
                return QwenOCRResponse(
                    success=False,
                    ocr_text="",
                    model_used=model,
                    processing_time_ms=round((time.time() - start_time) * 1000, 2),
                    error=f"OCR processing timeout ({config.OLLAMA_REQUEST_TIMEOUT}s exceeded)"
                )
            except httpx.RequestError as e:
                return QwenOCRResponse(
                    success=False,
                    ocr_text="",
                    model_used=model,
                    processing_time_ms=round((time.time() - start_time) * 1000, 2),
                    error=f"Network error: {str(e)}"
                )

    except Exception as e:
        return QwenOCRResponse(
            success=False,
            ocr_text="",
            model_used="qwen2.5vl:7b",
            processing_time_ms=round((time.time() - start_time) * 1000, 2),
            error=f"Server error: {str(e)}"
        )

@app.post("/v1/qwen/ocr-file", tags=["Qwen2.5-VL"], response_model=QwenOCRResponse)
async def qwen_ocr_file_upload(
    file: UploadFile = File(..., description="이미지 파일 (PNG, JPG, JPEG)"),
    prompt: str = "이 이미지의 모든 텍스트를 정확히 읽어주세요. 한국어, 영어, 숫자를 모두 포함해서 줄바꿈도 유지해주세요.",
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
            temperature=temperature,
            top_p=top_p
        )

        return await qwen_ocr_endpoint(request_obj, api_key)

    except Exception as e:
        return QwenOCRResponse(
            success=False,
            ocr_text="",
            model_used="qwen2.5vl:7b",
            processing_time_ms=round((time.time() - start_time) * 1000, 2),
            error=f"File processing error: {str(e)}"
        )

@app.get("/v1/health", tags=["System"])
async def health_check():
    """
    전체 시스템 상태 확인 (인증 불필요)
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        gpu0_status = "offline"
        gpu1_status = "offline"
        
        try:
            response = await client.get("http://ollama_gpu0:11434/api/tags")
            if response.status_code == 200:
                gpu0_status = "online"
        except:
            pass
            
        try:
            response = await client.get("http://ollama_gpu1:11434/api/tags")
            if response.status_code == 200:
                gpu1_status = "online"
        except:
            pass
    
    return {
        "status": "healthy" if gpu0_status == "online" and gpu1_status == "online" else "degraded",
        "gpu0_qwen": gpu0_status,
        "gpu1_gpt": gpu1_status,
        "models": {
            "qwen2.5vl:7b": "GPU 0 (RTX 3060)",
            "gpt-oss:20b": "GPU 1 (RTX 5060 Ti)"
        }
    }
