# Pydantic을 사용한 요청/응답 형식 정의
from pydantic import BaseModel
from typing import Any

class OllamaRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False
    options: dict[str, Any] = {}