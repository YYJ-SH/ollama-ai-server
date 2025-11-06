"""
🧪 Config 테스트
"""
from app import config


def test_supported_models():
    """지원 모델 목록 확인"""
    assert "qwen2.5vl:7b" in config.SUPPORTED_MODELS
    assert "gpt-oss:20b" in config.SUPPORTED_MODELS
    assert len(config.SUPPORTED_MODELS) == 2


def test_ollama_endpoints():
    """Ollama 엔드포인트 설정 확인"""
    assert "qwen2.5vl:7b" in config.OLLAMA_ENDPOINTS
    assert "gpt-oss:20b" in config.OLLAMA_ENDPOINTS
    
    # GPU 0 확인
    assert "ollama_gpu0" in config.OLLAMA_ENDPOINTS["qwen2.5vl:7b"]
    
    # GPU 1 확인
    assert "ollama_gpu1" in config.OLLAMA_ENDPOINTS["gpt-oss:20b"]


def test_request_timeout():
    """타임아웃 설정 확인"""
    assert hasattr(config, 'OLLAMA_REQUEST_TIMEOUT')
    assert config.OLLAMA_REQUEST_TIMEOUT >= 300.0


def test_database_file():
    """데이터베이스 파일 경로 확인"""
    assert config.DATABASE_FILE == "/app/database/api_server.db"
