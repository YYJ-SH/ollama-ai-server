#!/bin/bash

# 🧪 AI 서버 최적화 검증 스크립트
# 사용법: ./verify_optimization.sh

echo "🔍 AI 서버 최적화 검증 시작..."
echo ""

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SUCCESS=0
FAIL=0

# 1. Docker 컨테이너 상태 확인
echo "📦 1. Docker 컨테이너 상태 확인..."
if docker ps | grep -q "ollama_gpu0"; then
    echo -e "${GREEN}✅ ollama_gpu0: Running${NC}"
    ((SUCCESS++))
else
    echo -e "${RED}❌ ollama_gpu0: Not Running${NC}"
    ((FAIL++))
fi

if docker ps | grep -q "ollama_gpu1"; then
    echo -e "${GREEN}✅ ollama_gpu1: Running${NC}"
    ((SUCCESS++))
else
    echo -e "${RED}❌ ollama_gpu1: Not Running${NC}"
    ((FAIL++))
fi

if docker ps | grep -q "fastapi_gateway"; then
    echo -e "${GREEN}✅ fastapi_gateway: Running${NC}"
    ((SUCCESS++))
else
    echo -e "${RED}❌ fastapi_gateway: Not Running${NC}"
    ((FAIL++))
fi
echo ""

# 2. 모델 메모리 유지 확인
echo "🧠 2. 모델 메모리 유지 확인..."
GPU0_MODELS=$(docker exec ollama_gpu0 ollama ps 2>/dev/null)
if echo "$GPU0_MODELS" | grep -q "Forever"; then
    echo -e "${GREEN}✅ GPU 0: 모델이 영구 메모리에 유지됨 (Forever)${NC}"
    echo "$GPU0_MODELS"
    ((SUCCESS++))
else
    echo -e "${YELLOW}⚠️  GPU 0: 모델이 일시적으로 유지됨 (4 minutes)${NC}"
    echo -e "${YELLOW}    → OLLAMA_KEEP_ALIVE=-1 설정을 확인하세요${NC}"
    echo "$GPU0_MODELS"
    ((FAIL++))
fi
echo ""

GPU1_MODELS=$(docker exec ollama_gpu1 ollama ps 2>/dev/null)
if echo "$GPU1_MODELS" | grep -q "Forever"; then
    echo -e "${GREEN}✅ GPU 1: 모델이 영구 메모리에 유지됨 (Forever)${NC}"
    echo "$GPU1_MODELS"
    ((SUCCESS++))
else
    echo -e "${YELLOW}⚠️  GPU 1: 모델이 일시적으로 유지됨${NC}"
    echo "$GPU1_MODELS"
    ((FAIL++))
fi
echo ""

# 3. GPU 메모리 사용 확인
echo "💾 3. GPU 메모리 사용 확인..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader
    
    GPU0_MEM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0)
    GPU1_MEM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1)
    
    if [ "$GPU0_MEM" -gt 5000 ]; then
        echo -e "${GREEN}✅ GPU 0: ${GPU0_MEM}MB 사용 중 (모델 로드됨)${NC}"
        ((SUCCESS++))
    else
        echo -e "${RED}❌ GPU 0: ${GPU0_MEM}MB 사용 중 (모델이 로드되지 않음)${NC}"
        ((FAIL++))
    fi
    
    if [ "$GPU1_MEM" -gt 5000 ]; then
        echo -e "${GREEN}✅ GPU 1: ${GPU1_MEM}MB 사용 중 (모델 로드됨)${NC}"
        ((SUCCESS++))
    else
        echo -e "${YELLOW}⚠️  GPU 1: ${GPU1_MEM}MB 사용 중 (아직 미사용 또는 로드 중)${NC}"
        ((FAIL++))
    fi
else
    echo -e "${YELLOW}⚠️  nvidia-smi를 찾을 수 없습니다${NC}"
fi
echo ""

# 4. FastAPI Health Check
echo "🏥 4. FastAPI Health Check..."
HEALTH_RESPONSE=$(curl -s http://localhost:8010/v1/health 2>/dev/null)
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo -e "${GREEN}✅ FastAPI Health: healthy${NC}"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
    ((SUCCESS++))
else
    echo -e "${RED}❌ FastAPI Health: unhealthy 또는 응답 없음${NC}"
    echo "$HEALTH_RESPONSE"
    ((FAIL++))
fi
echo ""

# 5. 환경변수 확인
echo "⚙️  5. Docker Compose 환경변수 확인..."
if docker exec ollama_gpu0 printenv | grep -q "OLLAMA_KEEP_ALIVE"; then
    KEEP_ALIVE=$(docker exec ollama_gpu0 printenv OLLAMA_KEEP_ALIVE)
    if [ "$KEEP_ALIVE" = "-1" ]; then
        echo -e "${GREEN}✅ GPU 0: OLLAMA_KEEP_ALIVE=-1${NC}"
        ((SUCCESS++))
    else
        echo -e "${YELLOW}⚠️  GPU 0: OLLAMA_KEEP_ALIVE=$KEEP_ALIVE (권장: -1)${NC}"
        ((FAIL++))
    fi
else
    echo -e "${RED}❌ GPU 0: OLLAMA_KEEP_ALIVE 미설정${NC}"
    ((FAIL++))
fi

if docker exec ollama_gpu1 printenv | grep -q "OLLAMA_KEEP_ALIVE"; then
    KEEP_ALIVE=$(docker exec ollama_gpu1 printenv OLLAMA_KEEP_ALIVE)
    if [ "$KEEP_ALIVE" = "-1" ]; then
        echo -e "${GREEN}✅ GPU 1: OLLAMA_KEEP_ALIVE=-1${NC}"
        ((SUCCESS++))
    else
        echo -e "${YELLOW}⚠️  GPU 1: OLLAMA_KEEP_ALIVE=$KEEP_ALIVE (권장: -1)${NC}"
        ((FAIL++))
    fi
else
    echo -e "${RED}❌ GPU 1: OLLAMA_KEEP_ALIVE 미설정${NC}"
    ((FAIL++))
fi
echo ""

# 결과 요약
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 검증 결과 요약"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "통과: ${GREEN}$SUCCESS${NC} / 실패: ${RED}$FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 모든 최적화가 성공적으로 적용되었습니다!${NC}"
    echo ""
    echo "다음 단계:"
    echo "1. OCR 속도 테스트 실행"
    echo "2. 실제 이미지로 처리 시간 확인"
    echo "3. 모니터링 시작"
else
    echo -e "${YELLOW}⚠️  일부 항목에 문제가 있습니다.${NC}"
    echo ""
    echo "해결 방법:"
    echo "1. docker-compose.yml 환경변수 확인"
    echo "2. 컨테이너 재시작: docker-compose down && docker-compose up -d"
    echo "3. 로그 확인: docker logs fastapi_gateway"
    echo ""
    echo "자세한 내용은 OPTIMIZATION_GUIDE.md를 참고하세요."
fi
echo ""
