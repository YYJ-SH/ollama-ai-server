"""
🧪 FastAPI 앱 테스트
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthCheck:
    """헬스체크 테스트"""
    
    def test_health_endpoint(self):
        """헬스체크 엔드포인트 테스트"""
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded"]


class TestModelsEndpoint:
    """모델 리스트 테스트"""
    
    @pytest.fixture
    def api_key_headers(self):
        """API 키 헤더 (실제 키로 교체 필요)"""
        return {"X-API-Key": "test-api-key-change-this"}
    
    def test_models_without_auth(self):
        """인증 없이 모델 리스트 요청"""
        response = client.get("/v1/models")
        assert response.status_code == 422  # Missing header
    
    def test_models_with_auth(self, api_key_headers):
        """인증과 함께 모델 리스트 요청"""
        response = client.get("/v1/models", headers=api_key_headers)
        # API 키가 유효하지 않으면 401
        assert response.status_code in [200, 401]


class TestOCREndpoint:
    """OCR 엔드포인트 테스트"""
    
    @pytest.fixture
    def api_key_headers(self):
        return {"X-API-Key": "test-api-key-change-this"}
    
    @pytest.fixture
    def sample_image_base64(self):
        """테스트용 base64 이미지"""
        # 1x1 투명 PNG
        return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    def test_ocr_without_auth(self, sample_image_base64):
        """인증 없이 OCR 요청"""
        response = client.post(
            "/v1/qwen/ocr",
            json={"image_base64": sample_image_base64}
        )
        assert response.status_code == 422
    
    def test_ocr_with_auth(self, api_key_headers, sample_image_base64):
        """인증과 함께 OCR 요청"""
        response = client.post(
            "/v1/qwen/ocr",
            headers=api_key_headers,
            json={
                "image_base64": sample_image_base64,
                "prompt": "Extract text"
            }
        )
        # API 키가 유효하지 않으면 401, 유효하면 200
        assert response.status_code in [200, 401]
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "ocr_text" in data
            assert "processing_time_ms" in data


class TestGenerateEndpoint:
    """생성 엔드포인트 테스트"""
    
    @pytest.fixture
    def api_key_headers(self):
        return {"X-API-Key": "test-api-key-change-this"}
    
    def test_generate_without_auth(self):
        """인증 없이 생성 요청"""
        response = client.post(
            "/v1/generate",
            json={
                "model": "qwen2.5vl:7b",
                "prompt": "test"
            }
        )
        assert response.status_code == 422
    
    def test_generate_unsupported_model(self, api_key_headers):
        """지원하지 않는 모델 요청"""
        response = client.post(
            "/v1/generate",
            headers=api_key_headers,
            json={
                "model": "unsupported-model",
                "prompt": "test"
            }
        )
        # API 키 검증 후 모델 검증이므로 401 또는 400
        assert response.status_code in [400, 401]


# Integration Tests (실제 Ollama 서버 필요)
@pytest.mark.integration
class TestIntegration:
    """통합 테스트 (실제 서버 필요)"""
    
    @pytest.fixture
    def valid_api_key(self):
        """실제 유효한 API 키 (환경변수에서 로드)"""
        import os
        return os.getenv("TEST_API_KEY", "")
    
    @pytest.mark.skipif(
        not pytest.config.getoption("--run-integration"),
        reason="Integration tests disabled"
    )
    def test_full_ocr_flow(self, valid_api_key):
        """전체 OCR 플로우 테스트"""
        if not valid_api_key:
            pytest.skip("No valid API key provided")
        
        # TODO: 실제 OCR 테스트 구현
        pass


def pytest_addoption(parser):
    """pytest 옵션 추가"""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests"
    )
