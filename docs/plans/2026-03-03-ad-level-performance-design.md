# Ad(소재) 레벨 성과 리포트 추가 설계

## 배경

현재 주간 리포트는 AdSet 레벨까지만 성과를 표시한다. 하나의 AdSet 안에 여러 소재(Ad)가 있어서, 어떤 소재가 잘 되고 있는지 리포트에서 바로 확인할 수 없는 상태.

## 목표

- 소재(Ad)별 성과 테이블을 리포트에 추가
- 각 소재에 WINNING/WATCH/KILL 판정 표시
- DB 레벨 "판정", "Frequency" 속성 삭제 (소재별로 확인 가능하므로 불필요)

## 변경 범위

### 1. fetch_meta_ads.py — Ad 레벨 데이터 수집

- `fetch_ad_insights()` 함수 추가
- Meta Insights API `level="ad"` 호출
- 필드: ad_id, ad_name, impressions, clicks, spend, reach, frequency, cpc, ctr, actions
- 캠페인별로 그룹핑하여 반환

### 2. process_data.py — Ad 데이터 처리

- `process_ad_data()` 함수 추가
- 각 Ad의 CPC, CTR, 전환수 계산
- 캠페인별 `campaign['ads']` 배열에 저장
- 최종 JSON에 ads 배열 포함

### 3. send_to_notion.py — 판정 + 리포트 표시

**판정 로직** (meta-ads-automation의 judge.py에서 포팅):
- impressions < 100 → INSUFFICIENT (테이블에서 제외)
- frequency >= 3.0 → KILL
- ctr < 0.5% → KILL
- cpc > target_cpc × 2 → KILL
- frequency >= 2.0 → WATCH
- ctr >= 1.5% → WINNING
- 그 외 → WATCH

**리포트 섹션** ("📋 AdSet별 성과" 다음에 배치):

```
## 🎨 소재별 성과

| 소재 | 지출 | 노출 | 클릭 | CPC | CTR | 전환 | 판정 |
```

- 판정 칼럼: WINNING(초록)/WATCH(노랑)/KILL(빨강) 텍스트
- 노출 100 미만 소재는 테이블에서 제외

**DB 속성 변경**:
- "판정" select 속성: 코드에서 설정하지 않음 (Notion에서 수동 삭제)
- "Frequency" number 속성: 코드에서 설정하지 않음 (Notion에서 수동 삭제)

### 4. meta-ads-automation 정리

- `notion_reporter.py`의 "📊 성과 분석" 블록 append 로직은 비활성화 (reporter에서 직접 처리하므로)

## 판정 임계값 (config)

```python
WINNING_CTR = 1.5    # % 이상이면 WINNING
KILL_CTR = 0.5       # % 미만이면 KILL
TARGET_CPC = 500     # KRW, 2배 초과 시 KILL (1000 KRW)
WATCH_FREQUENCY = 2.0
KILL_FREQUENCY = 3.0
```

## 리포트 구조 (변경 후)

1. 📊 성과 요약 (기존)
2. 👥 연령대별 분석 (기존)
3. 🚻 성별 분석 (기존)
4. 📍 지역별 분석 (기존)
5. 📋 AdSet별 성과 (기존)
6. **🎨 소재별 성과** (신규)
7. 💡 주요 인사이트 & 액션 플랜 (기존)
