# ==================== 🚀 NEW: PaddleOCR 엔드포인트 (Client to paddleocr_service) ====================

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
    PaddleOCR 서비스를 호출하여 OCR을 수행하는 엔드포인트
    """
    async with httpx.AsyncClient() as client:
        try:
            # Read the file content
            file_content = await file.read()

            # Prepare the multipart form data for the upstream service
            files = {'file': (file.filename, file_content, file.content_type)}

            # Call the paddleocr_service
            # The service name in docker-compose is 'paddleocr_service' and it listens on port 8001
            response = await client.post("http://paddleocr_service:8001/ocr", files=files, timeout=300.0)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            
            return response.json() # Return the response from the PaddleOCR service

        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"PaddleOCR 서비스 연결 오류: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"PaddleOCR 서비스 오류: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"알 수 없는 오류 발생: {e}")