# qwen_remote_client_test.py - GPU 서버 테스트용

import requests
import base64
import time
from PIL import ImageGrab
import os

class QwenRemoteClient:
    """원격 Qwen2.5-VL 서버 클라이언트"""
    
    def __init__(self, server_url: str, api_key: str):
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    def test_connection(self):
        """서버 연결 테스트"""
        try:
            response = requests.get(
                f"{self.server_url}/v1/qwen/health",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✅ 서버 연결 성공!")
                print(f"📊 상태: {data.get('status')}")
                print(f"🤖 사용가능한 Qwen 모델: {data.get('available_qwen_models', [])}")
                return True
            else:
                print(f"❌ 서버 응답 오류: {response.status_code}")
                print(f"📝 응답: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 연결 실패: {e}")
            return False
    
    def image_to_base64(self, image_path: str) -> str:
        """이미지 파일을 base64로 인코딩"""
        try:
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode('utf-8')
        except Exception as e:
            print(f"이미지 인코딩 실패: {e}")
            return ""
    
    def screenshot_to_base64(self, bbox=None) -> str:
        """스크린샷을 찍고 base64로 인코딩"""
        try:
            screenshot = ImageGrab.grab(bbox=bbox)
            temp_path = "temp_screenshot.png"
            screenshot.save(temp_path)
            
            base64_str = self.image_to_base64(temp_path)
            os.remove(temp_path)  # 임시 파일 삭제
            
            return base64_str
        except Exception as e:
            print(f"스크린샷 실패: {e}")
            return ""
    
    def ocr_from_base64(self, image_base64: str, prompt: str = None, model: str = "qwen2.5vl:7b") -> dict:
        """Base64 이미지로 OCR 요청"""
        if not prompt:
            prompt = "이 이미지의 모든 텍스트를 정확히 읽어주세요. 한국어, 영어, 숫자를 모두 포함해서 줄바꿈도 유지해주세요."
        
        payload = {
            "image_base64": image_base64,
            "prompt": prompt,
            "model": model,
            "temperature": 0.1,
            "top_p": 0.9
        }
        
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.server_url}/v1/qwen/ocr",
                json=payload,
                headers=self.headers,
                timeout=60
            )
            
            request_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ OCR 성공! (요청시간: {request_time:.0f}ms, 처리시간: {result.get('processing_time_ms', 0)}ms)")
                print(f"📝 결과: {result.get('ocr_text', '')}")
                return result
            else:
                print(f"❌ OCR 실패: {response.status_code}")
                print(f"📝 에러: {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ OCR 요청 실패: {e}")
            return {"success": False, "error": str(e)}
    
    def ocr_from_file(self, file_path: str, prompt: str = None) -> dict:
        """파일 업로드 방식 OCR 요청"""
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'image/png')}
                data = {
                    'prompt': prompt or "이 이미지의 모든 텍스트를 정확히 읽어주세요.",
                    'model': 'qwen2.5vl:7b',  # 수정: 콜론 제거
                    'temperature': 0.1,
                    'top_p': 0.9
                }
                
                response = requests.post(
                    f"{self.server_url}/v1/qwen/ocr-file",
                    files=files,
                    data=data,
                    headers={'X-API-Key': self.api_key},  # Content-Type은 자동 설정됨
                    timeout=60
                )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 파일 OCR 성공! (처리시간: {result.get('processing_time_ms', 0)}ms)")
                print(f"📝 결과: {result.get('ocr_text', '')}")
                return result
            else:
                print(f"❌ 파일 OCR 실패: {response.status_code}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ 파일 OCR 요청 실패: {e}")
            return {"success": False, "error": str(e)}


def main():
    # 🔧 설정 (여기를 수정하세요!)
    SERVER_URL = "http://your-gpu-server.com:8000"  # 여기에 실제 서버 주소
    API_KEY = "your-api-key-here"  # 여기에 실제 API 키
    
    print("🔥 Qwen2.5-VL 원격 서버 테스트 시작!")
    print("=" * 50)
    
    client = QwenRemoteClient(SERVER_URL, API_KEY)
    
    # 1. 서버 연결 테스트
    print("1️⃣ 서버 연결 테스트...")
    if not client.test_connection():
        print("❌ 서버에 연결할 수 없습니다. 설정을 확인하세요.")
        return
    
    print("\n" + "=" * 50)
    
    # 2. 스크린샷 OCR 테스트
    print("2️⃣ 스크린샷 OCR 테스트 (3초 후 전체 화면 캡처)")
    time.sleep(3)
    
    screenshot_b64 = client.screenshot_to_base64()
    if screenshot_b64:
        print("📸 스크린샷 캡처 완료!")
        result = client.ocr_from_base64(screenshot_b64, "이 화면에서 모든 텍스트를 찾아 읽어주세요.")
        
        if result.get('success'):
            print(f"🎯 OCR 결과 길이: {len(result.get('ocr_text', ''))} 글자")
    
    print("\n" + "=" * 50)
    
    # 3. 특정 영역 OCR 테스트 (화면 중앙 400x300)
    print("3️⃣ 화면 중앙 부분 OCR 테스트")
    
    # 화면 중앙 영역 계산
    import win32api
    screen_width = win32api.GetSystemMetrics(0)
    screen_height = win32api.GetSystemMetrics(1)
    
    center_x, center_y = screen_width // 2, screen_height // 2
    bbox = (center_x - 200, center_y - 150, center_x + 200, center_y + 150)
    
    partial_b64 = client.screenshot_to_base64(bbox=bbox)
    if partial_b64:
        print(f"📸 부분 스크린샷 캡처 완료! ({bbox})")
        result = client.ocr_from_base64(
            partial_b64, 
            "이 이미지에서 버튼, 링크, 메뉴 등 클릭 가능한 UI 요소의 텍스트를 읽어주세요."
        )
    
    print("\n" + "=" * 50)
    
    # 4. 파일 업로드 OCR 테스트 (옵션)
    test_file = input("4️⃣ 테스트할 이미지 파일 경로 (Enter로 스킵): ").strip()
    if test_file and os.path.exists(test_file):
        print(f"📁 파일 OCR 테스트: {test_file}")
        result = client.ocr_from_file(test_file, "이 이미지의 모든 내용을 자세히 읽어주세요.")
    
    print("\n✅ 테스트 완료!")

# 간단한 성능 벤치마크 함수
def benchmark_test():
    """성능 벤치마크 테스트"""
    SERVER_URL = "http://your-gpu-server.com:8000"  
    API_KEY = "your-api-key-here"  
    
    client = QwenRemoteClient(SERVER_URL, API_KEY)
    
    if not client.test_connection():
        return
    
    print("🏃‍♂️ 성능 벤치마크 시작 (10회 테스트)")
    
    screenshot_b64 = client.screenshot_to_base64()
    if not screenshot_b64:
        print("❌ 스크린샷 실패")
        return
    
    times = []
    for i in range(10):
        print(f"테스트 {i+1}/10...", end=" ")
        start = time.time()
        result = client.ocr_from_base64(screenshot_b64)
        end = time.time()
        
        if result.get('success'):
            total_time = (end - start) * 1000
            times.append(total_time)
            print(f"✅ {total_time:.0f}ms")
        else:
            print("❌ 실패")
    
    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"\n📊 성능 결과:")
        print(f"평균: {avg_time:.0f}ms")
        print(f"최소: {min_time:.0f}ms")
        print(f"최대: {max_time:.0f}ms")

if __name__ == "__main__":
    choice = input("테스트 모드 선택 (1: 일반테스트, 2: 벤치마크): ").strip()
    
    if choice == "2":
        benchmark_test()
    else:
        main()