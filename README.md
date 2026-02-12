# Meta Ads → Notion Weekly Reporter

자동으로 Meta 광고 성과를 수집하여 Notion에 주간 리포트를 생성하는 시스템입니다.

## 주요 기능

- ✅ Meta Marketing API에서 지난 7일간 광고 성과 자동 수집
- ✅ 주요 메트릭 자동 계산 (CPC, CTR, CPA, ROAS)
- ✅ 캠페인별 성과 분석
- ✅ 오디언스 인사이트 (연령, 성별, 지역)
- ✅ Notion 데이터베이스에 구조화된 리포트 자동 생성
- ✅ GitHub Actions로 매주 월요일 09:00 KST 자동 실행
- ✅ Slack 알림 (성공/실패)

## 시간 절약 효과

- **수동 작업**: 주간 리포트 작성 약 2시간
- **자동화 후**: 약 10분 (90% 시간 절약)

---

## 초기 설정

### 1. 저장소 클론 및 가상환경 설정

```bash
cd /Users/leo/Downloads/Claude-Projects/meta-ads-notion-reporter

# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt
```

### 2. Meta Marketing API 설정

1. **Facebook 개발자 계정 생성**
   - https://developers.facebook.com/ 접속
   - "My Apps" → "Create App" 선택

2. **앱 생성 및 권한 설정**
   - 앱 타입: "Business" 선택
   - 앱 이름 입력 및 생성
   - "Marketing API" 추가

3. **Access Token 발급**
   - Tools → Graph API Explorer 접속
   - 권한 선택:
     - `ads_read`
     - `ads_management`
     - `read_insights`
   - "Generate Access Token" 클릭
   - **Long-lived Token 생성** (60일 유효):
     ```bash
     curl -X GET "https://graph.facebook.com/v19.0/oauth/access_token?\
       grant_type=fb_exchange_token&\
       client_id=YOUR_APP_ID&\
       client_secret=YOUR_APP_SECRET&\
       fb_exchange_token=YOUR_SHORT_LIVED_TOKEN"
     ```

4. **광고 계정 ID 확인**
   - Meta Ads Manager 접속
   - 계정 설정 → 광고 계정 ID 확인 (예: `act_123456789`)

### 3. Notion API 설정

1. **Notion Integration 생성**
   - https://www.notion.so/my-integrations 접속
   - "New integration" 클릭
   - 이름: "Meta Ads Reporter"
   - Capabilities:
     - ✅ Read content
     - ✅ Update content
     - ✅ Insert content
   - "Submit" 후 "Internal Integration Token" 복사

2. **Parent Page 생성**
   - Notion에서 리포트를 저장할 페이지 생성 (예: "마케팅 리포트")
   - 페이지 우측 상단 "..." → "Connections" → Integration 추가
   - 페이지 URL에서 ID 추출:
     ```
     https://www.notion.so/workspace/Page-Name-{PAGE_ID}?...
     ```

### 4. 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집하여 API 키 입력
nano .env
```

**필수 환경 변수:**
- `META_APP_ID`: Meta 앱 ID
- `META_APP_SECRET`: Meta 앱 시크릿
- `META_ACCESS_TOKEN`: Long-lived Access Token
- `META_AD_ACCOUNT_ID`: 광고 계정 ID (예: `act_123456789`)
- `NOTION_TOKEN`: Notion Integration Token
- `NOTION_PARENT_PAGE_ID`: Notion Parent Page ID
- `SLACK_WEBHOOK_URL`: (선택) Slack Webhook URL

### 5. Notion 데이터베이스 생성 (최초 1회)

```bash
python scripts/create_notion_db.py
```

출력 예시:
```
✅ Notion 데이터베이스 생성 완료!
   Database ID: a1b2c3d4e5f6...
   URL: https://www.notion.so/a1b2c3d4e5f6

   config/config.json에 저장되었습니다.
```

---

## 사용법

### 수동 실행

#### 1단계: Meta 데이터 수집
```bash
python scripts/fetch_meta_ads.py
```

#### 2단계: 데이터 처리
```bash
python scripts/process_data.py
```

#### 3단계: Notion 업데이트
```bash
python scripts/send_to_notion.py
```

#### 전체 파이프라인 실행
```bash
python scripts/run_weekly_report.py
```

### 자동 실행 (GitHub Actions)

1. **GitHub Secrets 설정**
   - 저장소 → Settings → Secrets and variables → Actions
   - 다음 secrets 추가:
     - `META_APP_ID`
     - `META_APP_SECRET`
     - `META_ACCESS_TOKEN`
     - `META_AD_ACCOUNT_ID`
     - `NOTION_TOKEN`
     - `NOTION_PARENT_PAGE_ID`
     - `NOTION_DATABASE_ID`
     - `SLACK_WEBHOOK_URL` (선택)

2. **워크플로우 활성화**
   - Actions 탭 → "Weekly Meta Ads Report" → "Enable workflow"

3. **수동 실행 테스트**
   - Actions 탭 → "Weekly Meta Ads Report" → "Run workflow"

4. **자동 스케줄**
   - 매주 월요일 00:00 UTC (09:00 KST) 자동 실행

---

## Notion 리포트 구조

### 데이터베이스 속성

| 속성명 | 타입 | 설명 |
|--------|------|------|
| 리포트 제목 | Title | "Week of YYYY-MM-DD" |
| 주차 | Date | 시작일~종료일 |
| 총 지출 | Number | 주간 총 광고비 (원) |
| 총 노출 | Number | 주간 총 노출수 |
| 총 클릭 | Number | 주간 총 클릭수 |
| 평균 CPC | Number | 클릭당 비용 (원) |
| 평균 CTR | Number | 클릭률 (%) |
| 총 전환수 | Number | 주간 총 전환 |
| 평균 CPA | Number | 전환당 비용 (원) |
| ROAS | Number | 광고 수익률 |
| 캠페인 수 | Number | 활성 캠페인 개수 |
| 상태 | Select | 완료/진행중/검토필요 |

### 페이지 콘텐츠

```markdown
# Week of 2026-02-03

## 주간 요약
> 총 지출: 1,250,000원
> 총 노출: 485,000회
> 평균 ROAS: 3.2

## 캠페인별 성과
| 캠페인명 | 지출 | 노출 | 클릭 | CPC | CTR | 전환 | ROAS |
|---------|------|------|------|-----|-----|------|------|
| ...     | ...  | ...  | ...  | ... | ... | ...  | ...  |

## 오디언스 인사이트
### 연령대별 분석
### 성별 분석
### 지역별 분석
```

---

## 트러블슈팅

### Meta API 인증 실패
```
Error: (#190) Invalid OAuth 2.0 Access Token
```

**해결 방법:**
1. Access Token이 만료되었는지 확인 (60일 유효)
2. Long-lived Token 재발급
3. `.env` 파일에 새 토큰 업데이트

### Notion API 권한 오류
```
Error: Could not find database with ID
```

**해결 방법:**
1. Parent Page에 Integration이 연결되어 있는지 확인
2. `NOTION_PARENT_PAGE_ID`가 올바른지 확인
3. Integration에 "Insert content" 권한이 있는지 확인

### 데이터 수집 실패
```
Error: Ad account not found
```

**해결 방법:**
1. `META_AD_ACCOUNT_ID`가 `act_` 접두사를 포함하는지 확인
2. 계정에 대한 접근 권한이 있는지 확인
3. Meta Business Manager에서 계정 상태 확인

### GitHub Actions 실패
```
Error: Secret not found
```

**해결 방법:**
1. GitHub Secrets이 모두 설정되어 있는지 확인
2. Secret 이름이 `.github/workflows/weekly-report.yml`과 일치하는지 확인
3. `config.json`의 `database_id`가 Secret에 추가되었는지 확인

---

## 로그 확인

```bash
# 전체 로그 보기
cat logs/automation.log

# 최근 로그 보기
tail -n 50 logs/automation.log

# 에러 로그만 보기
grep "ERROR" logs/automation.log
```

---

## 라이선스

MIT License

---

## 지원

문제가 발생하거나 기능 요청이 있으면 이슈를 생성해주세요.
