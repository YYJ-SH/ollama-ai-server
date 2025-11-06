# 설정값 관리

# 🔥 최적화: 각 GPU에 고정 모델 할당
OLLAMA_ENDPOINTS = {
    # GPU 0 (RTX 3060) - Qwen2.5-VL 전용
    "qwen2.5vl:7b": "http://ollama_gpu0:11434",
    
    # GPU 1 (RTX 5060 Ti) - GPT-OSS 전용
    "gpt-oss:20b": "http://ollama_gpu1:11434"
}

# 허용된 모델 목록 (고정 2개만)
SUPPORTED_MODELS = set(OLLAMA_ENDPOINTS.keys())

# 데이터베이스 파일 위치
DATABASE_FILE = "/app/database/api_server.db"

# Fallback용 기본 Ollama URL
OLLAMA_BASE_URL = "http://ollama_gpu0:11434"

# 🔥 타임아웃 설정 (기존 120초 → 300초)
OLLAMA_REQUEST_TIMEOUT = 300.0
