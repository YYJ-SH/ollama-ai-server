# ⚡ 빠른 적용 가이드 (Quick Start)

## 🎯 핵심 문제
- **OCR이 2분 이상 걸림** → 모델이 계속 재로딩됨
- **타임아웃 120초** → 처리 완료 전 에러 발생

## 🚀 3단계 해결책

### 1️⃣ Docker Compose 수정 (30초)
```bash
cd /home/user/ollama-ai-server
nano docker-compose.production.yml
```

**ollama_gpu0과 ollama_gpu1의 environment에 추가:**
```yaml
environment:
  - NVIDIA_VISIBLE_DEVICES=0  # 또는 1
  - OLLAMA_KEEP_ALIVE=-1              # 🔥 추가
  - OLLAMA_MAX_LOADED_MODELS=1        # 🔥 추가
  - OLLAMA_NUM_PARALLEL=4             # 🔥 추가
```

### 2️⃣ Config 수정 (10초)
```bash
nano fastapi_app/app/config.py
```

**파일 끝에 추가:**
```python
OLLAMA_REQUEST_TIMEOUT = 300.0  # 🔥 추가
```

### 3️⃣ 재시작 (2분)
```bash
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.production.yml build fastapi_app
docker-compose -f docker-compose.production.yml up -d
docker logs -f fastapi_gateway  # 로그 확인
```

---

## ✅ 검증
```bash
# 1. 모델이 영구 유지되는지 확인
docker exec -it ollama_gpu0 bash
ollama ps
# → UNTIL 열에 "Forever" 보이면 성공!

# 2. GPU 메모리 확인
nvidia-smi
# → GPU 0: ~7.5GB, GPU 1: ~10GB 사용 중이면 OK

# 3. 속도 테스트
# OCR 요청 보내보기
# → processing_time_ms가 2000-5000ms면 성공!
```

---

## 📊 예상 결과
| | 현재 | 적용 후 |
|---|---|---|
| OCR 시간 | 2분+ | **3-5초** ✨ |
| 모델 로딩 | 매 4분마다 | 서버 시작시 1회 |
| 처리 성공률 | ~50% (타임아웃) | ~99% |

---

## 🆘 문제 발생시
```bash
# 로그 확인
docker logs fastapi_gateway --tail 100
docker logs ollama_gpu0 --tail 100

# 재시작
docker-compose restart ollama_gpu0 ollama_gpu1 fastapi_app
```

**상세 가이드는 `OPTIMIZATION_GUIDE.md` 참고!**
