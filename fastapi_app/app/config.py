# 설정값 관리

# 모델에 따라 다른 Ollama 서버로 라우팅
OLLAMA_ENDPOINTS = {
    "llama3:7b": "http://ollama_gpu0:11434",
    "qwen2.5vl:7b": "http://ollama_gpu0:11434",
    "gpt-oss:20b": "http://ollama_gpu1:11434"
}

SUPPORTED_MODELS = set(OLLAMA_ENDPOINTS.keys())

DATABASE_FILE = "/app/database/api_server.db"
