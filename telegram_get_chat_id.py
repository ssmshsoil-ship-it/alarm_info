import os
import requests


token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not token:
    raise SystemExit("TELEGRAM_BOT_TOKEN 환경변수를 먼저 설정하세요.")

url = f"https://api.telegram.org/bot{token}/getUpdates"
data = requests.get(url, timeout=20).json()

print("아래 결과에서 message.chat.id 값을 TELEGRAM_CHAT_ID로 사용하세요.")
print(data)
