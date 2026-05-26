# kFarmAI 알람정보 테스트앱

상토, 비료, 퇴비, 종자, 농약, 농업e지, 농업 보조사업 관련 정보를 수집해서 `alerts.json`으로 저장하고, 텔레그램으로 하루 2회 알림을 보내는 개인 테스트앱입니다.

## 파일

- `index.html`: 모바일용 알람정보 화면
- `alerts.json`: 수집된 알람 데이터
- `sources.json`: 수집 키워드와 RSS 소스
- `collector.py`: 수집 및 텔레그램 발송 스크립트
- `requirements.txt`: Python 의존성
- `.github/workflows/daily-alerts.yml`: GitHub Actions 자동 실행 설정

## 로컬 실행

```powershell
pip install -r requirements.txt
python collector.py
```

텔레그램까지 테스트할 때:

```powershell
$env:TELEGRAM_BOT_TOKEN="봇토큰"
$env:TELEGRAM_CHAT_ID="채팅방ID"
python collector.py --send-telegram
```

## GitHub Pages 사용

1. 새 GitHub repo에 이 폴더의 파일을 올립니다.
2. `Settings > Pages`에서 `Deploy from a branch`, `main`, `/root`를 선택합니다.
3. `https://계정명.github.io/repo명/` 주소로 접속합니다.

## 텔레그램 설정

1. Telegram에서 `BotFather` 검색
2. `/newbot`으로 봇 생성
3. 생성한 봇에게 텔레그램에서 아무 메시지나 1개 보냅니다.
4. 발급받은 토큰을 GitHub repo의 `Settings > Secrets and variables > Actions`에 저장
   - 이름: `TELEGRAM_BOT_TOKEN`
5. 로컬에서 chat id를 확인합니다.

```powershell
$env:TELEGRAM_BOT_TOKEN="봇토큰"
python telegram_get_chat_id.py
```

6. 출력 결과에서 `message.chat.id` 값을 확인해서 Secret으로 저장합니다.
   - 이름: `TELEGRAM_CHAT_ID`
7. GitHub Actions에서 `daily-alerts` workflow를 수동 실행하거나 예약 실행을 기다립니다.

## 자동 실행 시간

GitHub Actions cron은 UTC 기준입니다.

- `0 22 * * *` = 한국시간 오전 7시
- `0 5 * * *` = 한국시간 오후 2시

## 주의

- 첫 버전은 기사/공고의 제목과 RSS 요약만 사용합니다.
- 신청기간, 금액, 대상자, 링크는 반드시 원문과 담당기관을 재확인해야 합니다.
- 원문 전문을 저장하지 않고 요약과 링크 중심으로 표시합니다.
- 수집 품질은 `sources.json`의 키워드와 RSS 주소를 조정하면서 개선합니다.
