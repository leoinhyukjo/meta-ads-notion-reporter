# Ad(소재) 레벨 성과 리포트 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 주간 리포트에 소재(Ad)별 성과 테이블 + WINNING/WATCH/KILL 판정을 추가하고, DB에서 불필요한 판정/Frequency 속성을 제거한다.

**Architecture:** `fetch_meta_ads.py`에 Ad 레벨 API 호출 추가 → `process_data.py`에 Ad 데이터 처리 추가 → `send_to_notion.py`에 판정 로직 + 소재 테이블 블록 생성 추가. 기존 AdSet 패턴을 그대로 따르며, 판정 로직은 `meta-ads-automation/judge.py`에서 포팅.

**Tech Stack:** Python 3, Meta Marketing API v19.0, Notion API (notion-client)

---

### Task 1: fetch_meta_ads.py — Ad 레벨 데이터 수집 추가

**Files:**
- Modify: `scripts/fetch_meta_ads.py`

**Step 1: `fetch_ad_insights()` 함수 추가**

`fetch_adset_insights()` (line 208-247) 바로 뒤에 추가. 동일 패턴으로 `level='ad'` 사용.

```python
def fetch_ad_insights(ad_account_id, date_range, access_token):
    """Ad(소재) 레벨 성과 데이터 수집"""
    api_version = 'v19.0'
    base_url = f'https://graph.facebook.com/{api_version}'

    fields = [
        'campaign_id',
        'campaign_name',
        'adset_id',
        'adset_name',
        'ad_id',
        'ad_name',
        'impressions',
        'clicks',
        'spend',
        'reach',
        'frequency',
        'cpc',
        'cpm',
        'ctr',
        'actions',
        'action_values',
    ]

    params = {
        'access_token': access_token,
        'fields': ','.join(fields),
        'time_range': json.dumps(date_range),
        'level': 'ad',
        'limit': 500
    }

    print("📊 Ad(소재) 인사이트 수집 중...")
    url = f'{base_url}/{ad_account_id}/insights'
    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise Exception(f"Meta API 에러 (Ad): {response.status_code} - {response.text}")

    ad_data = response.json().get('data', [])
    print(f"   ✅ {len(ad_data)}개 Ad 데이터 수집 완료")
    return ad_data
```

**Step 2: `main()` 함수에서 호출 추가**

`main()` 내 데이터 수집 부분 (line 282-284) 뒤에 추가:

```python
# 기존 코드 (line 282-284)
campaign_data = fetch_campaign_insights(ad_account_id, date_range, access_token)
audience_data = fetch_audience_insights(ad_account_id, date_range, access_token)
adset_data = fetch_adset_insights(ad_account_id, date_range, access_token)
# 추가
ad_data = fetch_ad_insights(ad_account_id, date_range, access_token)
```

`full_data` dict (line 287-301)에 ads 추가:

```python
full_data = {
    'collected_at': datetime.now().isoformat(),
    'date_range': date_range,
    'ad_account_id': ad_account_id,
    'campaigns': campaign_data,
    'adsets': adset_data,
    'ads': ad_data,                    # 추가
    'audience': audience_data,
    'summary': {
        'total_campaigns': len(campaign_data),
        'total_adsets': len(adset_data),
        'total_ads': len(ad_data),     # 추가
        'total_age_segments': len(audience_data.get('age', [])),
        'total_gender_segments': len(audience_data.get('gender', [])),
        'total_region_segments': len(audience_data.get('region', []))
    }
}
```

**Step 3: 수집 완료 로그에 Ad 수 추가**

print 문 (line 311-313 근처):

```python
print(f"   총 캠페인: {full_data['summary']['total_campaigns']}개")
print(f"   총 Ad: {full_data['summary']['total_ads']}개")  # 추가
```

**Step 4: 커밋**

```bash
cd /Users/leo/Downloads/Claude-Projects/meta-ads-notion-reporter
git add scripts/fetch_meta_ads.py
git commit -m "feat: add Ad-level insights fetching from Meta API"
```

---

### Task 2: process_data.py — Ad 데이터 처리 추가

**Files:**
- Modify: `scripts/process_data.py`

**Step 1: `process_ad_data()` 함수 추가**

`process_adset_data()` (line 210-252) 뒤에 추가. 동일 패턴:

```python
def process_ad_data(raw_ads):
    """Ad(소재) 데이터를 캠페인별로 그룹화하여 처리"""
    print("📊 Ad 데이터 처리 중...")

    by_campaign: dict[str, list] = {}

    for ad in raw_ads:
        cid = ad.get('campaign_id', 'unknown')
        if cid not in by_campaign:
            by_campaign[cid] = []

        impressions = safe_int(ad.get('impressions', 0))
        clicks = safe_int(ad.get('clicks', 0))
        spend = round(safe_float(ad.get('spend', 0)), 2)

        # 전환 추출
        actions = ad.get('actions', [])
        lead = extract_actions(actions, 'lead')
        purchase = extract_actions(actions, 'purchase')
        total_conversions = lead + purchase

        by_campaign[cid].append({
            'ad_id': ad.get('ad_id'),
            'ad_name': ad.get('ad_name', ''),
            'adset_name': ad.get('adset_name', ''),
            'impressions': impressions,
            'clicks': clicks,
            'spend': spend,
            'reach': safe_int(ad.get('reach', 0)),
            'frequency': round(safe_float(ad.get('frequency', 0)), 2),
            'cpc': round(spend / clicks, 2) if clicks > 0 else 0,
            'ctr': round(clicks / impressions * 100, 2) if impressions > 0 else 0,
            'conversions': total_conversions,
        })

    # 각 캠페인 내 지출 순 정렬
    for cid in by_campaign:
        by_campaign[cid].sort(key=lambda x: x['spend'], reverse=True)

    total = sum(len(v) for v in by_campaign.values())
    print(f"   ✅ Ad 데이터 처리 완료 ({total}개 Ad, {len(by_campaign)}개 캠페인)")
    return by_campaign
```

**Step 2: `main()`에서 Ad 처리 호출 + 캠페인 매핑 추가**

`main()` 내 AdSet 처리 (line 329) 다음에:

```python
# 기존 코드
adset_by_campaign = process_adset_data(raw_data.get('adsets', []))
# 추가
ad_by_campaign = process_ad_data(raw_data.get('ads', []))
```

캠페인 매핑 루프 (line 332-337)에 ads 추가:

```python
for campaign in processed_campaigns:
    cid = campaign['campaign_id']
    campaign['audience'] = audience_by_campaign.get(cid, {
        'age': [], 'gender': [], 'region': []
    })
    campaign['adsets'] = adset_by_campaign.get(cid, [])
    campaign['ads'] = ad_by_campaign.get(cid, [])  # 추가
```

**Step 3: 커밋**

```bash
git add scripts/process_data.py
git commit -m "feat: add Ad-level data processing grouped by campaign"
```

---

### Task 3: send_to_notion.py — 판정 로직 + 소재별 성과 테이블 추가

**Files:**
- Modify: `scripts/send_to_notion.py`

**Step 1: 판정 로직 추가**

파일 상단 (import 후, `load_config()` 전)에 판정 상수 + 함수 추가:

```python
# ── 소재 판정 로직 ──────────────────────────────────────────
# meta-ads-automation/judge.py에서 포팅
MIN_IMPRESSIONS = 100

# 임계값 (계정 통화 기준 — 현재 USD)
WINNING_CTR = 1.5     # % 이상이면 WINNING
KILL_CTR = 0.5        # % 미만이면 KILL
TARGET_CPC = 2.0      # USD, 2배 초과($4.0) 시 KILL
WATCH_FREQUENCY = 2.0
KILL_FREQUENCY = 3.0


def judge_ad(ad):
    """소재 성과 판정. 반환: 'WINNING' | 'WATCH' | 'KILL' | None(데이터 부족)"""
    if ad.get('impressions', 0) < MIN_IMPRESSIONS:
        return None  # 테이블에서 제외

    ctr = ad.get('ctr', 0)
    cpc = ad.get('cpc', 0)
    freq = ad.get('frequency', 0)

    if freq >= KILL_FREQUENCY:
        return 'KILL'
    if ctr < KILL_CTR:
        return 'KILL'
    if TARGET_CPC > 0 and cpc > TARGET_CPC * 2:
        return 'KILL'
    if freq >= WATCH_FREQUENCY:
        return 'WATCH'
    if ctr >= WINNING_CTR:
        return 'WINNING'
    return 'WATCH'
```

**Step 2: `create_ad_blocks()` 함수 추가**

`create_adset_blocks()` (line 253-286) 바로 뒤에 추가:

```python
def create_ad_blocks(ads):
    """소재별 성과 테이블 블록 생성 (판정 포함)"""
    if not ads:
        return []

    # 판정 실행 + 데이터 부족(None) 소재 제외
    judged = []
    for ad in ads:
        verdict = judge_ad(ad)
        if verdict is not None:
            ad['verdict'] = verdict
            judged.append(ad)

    if not judged:
        return []

    blocks = [_heading(2, "🎨 소재별 성과")]

    header = {
        "object": "block",
        "type": "table_row",
        "table_row": {"cells": [
            [_text("소재", bold=True)], [_text("지출", bold=True)],
            [_text("노출", bold=True)], [_text("클릭", bold=True)],
            [_text("CPC", bold=True)], [_text("CTR", bold=True)],
            [_text("전환", bold=True)], [_text("판정", bold=True)],
        ]}
    }
    rows = [header]
    for ad in judged:
        verdict = ad['verdict']
        verdict_color = {'WINNING': 'green', 'WATCH': 'yellow', 'KILL': 'red'}.get(verdict, 'default')
        # 판정 셀만 색상 적용
        verdict_cell = [_text(verdict, bold=True, color=verdict_color)]

        row = {
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": [
                [_text(ad['ad_name'])],
                [_text(f"${ad['spend']:,.2f}")],
                [_text(f"{ad['impressions']:,}")],
                [_text(f"{ad['clicks']:,}")],
                [_text(f"${ad['cpc']:.2f}")],
                [_text(f"{ad['ctr']:.2f}%")],
                [_text(str(ad.get('conversions', 0)))],
                verdict_cell,
            ]}
        }
        rows.append(row)

    blocks.append({
        "object": "block", "type": "table",
        "table": {"table_width": 8, "has_column_header": True, "has_row_header": False, "children": rows}
    })
    return blocks
```

**Step 3: `create_campaign_content_blocks()`에서 소재 블록 호출**

line 245 (`blocks.extend(create_adset_blocks(...))`) 다음에 추가:

```python
    # ── AdSet별 성과 ──
    blocks.extend(create_adset_blocks(campaign.get('adsets', [])))

    # ── 소재별 성과 ── (추가)
    blocks.extend(create_ad_blocks(campaign.get('ads', [])))

    # ── 인사이트 & 액션 플랜 ──
    blocks.extend(create_campaign_insights_blocks(campaign))
```

**Step 4: DB 속성에서 판정/Frequency 제거**

`create_campaign_page_properties()` (line 69-102)에서 이미 "판정"과 "Frequency"는 설정하지 않으므로 코드 변경 불필요. Notion DB에서 수동 삭제만 필요.

**Step 5: 커밋**

```bash
git add scripts/send_to_notion.py
git commit -m "feat: add Ad-level verdict table to weekly report"
```

---

### Task 4: 통합 테스트 — 로컬에서 전체 파이프라인 실행

**Step 1: 데이터 수집 단독 테스트**

```bash
cd /Users/leo/Downloads/Claude-Projects/meta-ads-notion-reporter
python scripts/fetch_meta_ads.py
```

Expected: `data/raw/ads_data_2026-03-03.json`에 `ads` 배열 포함 확인

**Step 2: JSON에 Ad 데이터 확인**

```bash
python -c "
import json
with open('data/raw/ads_data_2026-03-03.json') as f:
    d = json.load(f)
print(f'ads count: {len(d.get(\"ads\", []))}')
if d.get('ads'):
    print(f'sample: {d[\"ads\"][0].get(\"ad_name\", \"\")}')
"
```

**Step 3: 데이터 처리 단독 테스트**

```bash
python scripts/process_data.py
```

Expected: `data/processed/weekly_report_2026-03-03.json`의 각 캠페인에 `ads` 배열 포함 확인

**Step 4: Notion 업데이트 테스트**

```bash
python scripts/send_to_notion.py
```

Expected: Notion 리포트 페이지에 "🎨 소재별 성과" 테이블 표시, 각 행에 판정(WINNING/WATCH/KILL) 색상 포함

**Step 5: 커밋 (통합 테스트 통과 후)**

이미 Task 1-3에서 커밋 완료. 문제 있으면 이 시점에서 수정 + 커밋.

---

### Task 5: Notion DB 속성 정리 + meta-ads-automation 정리

**Step 1: Notion DB에서 판정/Frequency 속성 삭제**

Leo님이 Notion에서 수동으로 삭제:
- "판정" select 속성
- "Frequency" number 속성

**Step 2: meta-ads-automation의 notion_reporter.py 비활성화 확인**

`meta-ads-automation`에서 리포트에 판정 블록을 append하는 로직이 있지만, reporter에서 직접 처리하므로 더 이상 실행 불필요. launchd의 `run_analyze.py` 스케줄에서 Notion 리포트 업데이트 부분을 비활성화하거나, 중복 실행해도 "📊 성과 분석" 블록이 없으면 무시되므로 우선 방치 가능.

---

## 주의사항

- **판정 임계값 통화**: 현재 리포트가 USD 기준이므로 `TARGET_CPC = 2.0` (USD). 변경 필요 시 `send_to_notion.py` 상단 상수 수정.
- **Notion 테이블 셀 색상**: Notion API에서 테이블 셀의 rich_text에 `color` annotation을 지원함. 판정 텍스트에 green/yellow/red 적용.
- **INSUFFICIENT 소재**: 노출 100 미만 소재는 테이블에서 아예 제외 (데이터 부족으로 판정 불가).
