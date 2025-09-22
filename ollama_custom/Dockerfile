# Ollama 공식 이미지를 기반으로 시작
FROM ollama/ollama

# 우리가 만든 Modelfile을 컨테이너 안의 특정 경로로 복사
COPY Hybrid-Llama3.Modelfile /

# 컨테이너가 시작될 때, 모델을 자동으로 생성하고 서버를 실행하는 스크립트를 실행
CMD ["sh", "-c", "/bin/ollama serve & sleep 5 && /bin/ollama create llama3-hybrid -f /Hybrid-Llama3.Modelfile && wait"]