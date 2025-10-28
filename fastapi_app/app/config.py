# 설정값 관리

# 모델에 따라 다른 Ollama 서버로 라우팅
OLLAMA_ENDPOINTS = {
    "llama3:latest": "http://ollama_gpu0:11434",
    "qwen2.5vl:7b": "http://ollama_gpu0:11434",
    "qwen2.5vl:3b": "http://ollama_gpu0:11434",
    "exaone3.5:7.8b": "http://ollama_gpu0:11434",
    "gpt-oss:20b": "http://ollama_gpu1:11434"
}

# 허용된 모델 목록
SUPPORTED_MODELS = set(OLLAMA_ENDPOINTS.keys())

# 데이터베이스 파일 위치
DATABASE_FILE = "/app/database/api_server.db"

# Fallback용 기본 Ollama URL
OLLAMA_BASE_URL = "http://ollama_gpu0:11434"