from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from paddleocr import PaddleOCR
import numpy as np
from PIL import Image
import io
import time

app = FastAPI(
    title="PaddleOCR Service",
    description="A dedicated service for PaddleOCR processing."
)

# PaddleOCR 인스턴스 초기화 (GPU 사용, 한국어+영어 모델)
# 서버 시작 시 한 번만 로드되도록 전역으로 선언
try:
    print("Initializing PaddleOCR...")
    # use_gpu=True if GPU is available and configured in Docker
    paddle_ocr_instance = PaddleOCR(use_angle_cls=True, lang='korean', use_gpu=True) # Start with use_gpu=False for broader compatibility
    print("PaddleOCR initialized successfully.")
except Exception as e:
    print(f"Error initializing PaddleOCR: {e}")
    paddle_ocr_instance = None
    # Optionally, raise an exception here to prevent the app from starting if OCR is critical
    # raise RuntimeError(f"Failed to initialize PaddleOCR: {e}")

class PaddleOCRResponse(BaseModel):
    success: bool
    results: Optional[List[dict]] = None
    processing_time_ms: float
    error: Optional[str] = None

@app.post("/ocr", response_model=PaddleOCRResponse)
async def ocr_endpoint(
    file: UploadFile = File(..., description="이미지 파일 (PNG, JPG, JPEG)")
):
    """
    PaddleOCR을 사용한 고성능 OCR 엔드포인트
    - 이미지 파일을 직접 업로드하여 OCR 수행
    """
    if not paddle_ocr_instance:
        raise HTTPException(status_code=500, detail="PaddleOCR is not initialized. Check service logs for errors.")

    start_time = time.time()

    # 파일 타입 검증
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Only image files are supported")

    try:
        contents = await file.read()
        img = Image.open(io.BytesIO(contents))
        img_np = np.array(img)

        result = paddle_ocr_instance.ocr(img_np, cls=True)
        
        processing_time = (time.time() - start_time) * 1000

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