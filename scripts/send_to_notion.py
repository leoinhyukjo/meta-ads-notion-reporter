#!/usr/bin/env python3
"""
Notion 리포트 업데이트 스크립트

캠페인별 개별 페이지를 생성합니다.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from notion_client import Client

# 프로젝트 루트 디렉토리
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 환경 변수 로드
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))


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


def load_config():
    """config.json에서 database_id 로드"""
    config_path = os.path.join(PROJECT_ROOT, 'config', 'config.json')

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            "config.json 파일이 없습니다.\n"
            "먼저 create_notion_db.py를 실행하여 데이터베이스를 생성하세요."
        )

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    return config.get('notion_database_id')


def get_latest_processed_data():
    """data/processed/에서 가장 최근 처리된 데이터 로드"""
    processed_dir = os.path.join(PROJECT_ROOT, 'data', 'processed')
    json_files = list(Path(processed_dir).glob('weekly_report_*.json'))

    if not json_files:
        raise FileNotFoundError("data/processed/ 디렉토리에 처리된 데이터 파일이 없습니다.")

    latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
    print(f"📂 처리된 데이터 로드: {latest_file}")

    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data


def ensure_campaign_property(notion, database_id):
    """DB에 '캠페인명' 속성이 없으면 추가"""
    db = notion.databases.retrieve(database_id=database_id)
    if "캠페인명" not in db.get("properties", {}):
        print("📝 DB에 '캠페인명' 속성 추가 중...")
        notion.databases.update(
            database_id=database_id,
            properties={"캠페인명": {"select": {}}}
        )
        print("   ✅ '캠페인명' 속성 추가 완료")


def create_campaign_page_properties(campaign, date_range, manual_conversions=None):
    """캠페인별 Notion 페이지 속성 생성

    총 전환수는 수동 입력값을 보존합니다 (픽셀 미설치).
    manual_conversions가 제공되면 CPA를 재계산합니다.
    """
    name = campaign['campaign_name']
    short_name = name.replace("새 ", "").replace(" 캠페인", "")
    week_title = short_name

    props = {
        "리포트 제목": {
            "title": [{"text": {"content": week_title}}]
        },
        "기간": {
            "date": {"start": date_range['since'], "end": date_range['until']}
        },
        "캠페인명": {
            "select": {"name": name}
        },
        "총 지출": {"number": campaign['spend']},
        "총 노출": {"number": campaign['impressions']},
        "총 클릭": {"number": campaign['clicks']},
        "평균 CPC": {"number": campaign['cpc']},
        "평균 CTR": {"number": campaign['ctr'] / 100 if campaign['ctr'] > 1 else campaign['ctr']},
        "상태": {"select": {"name": "완료"}},
    }

    # 수동 전환수가 있으면 CPA 재계산
    if manual_conversions is not None:
        cpa = campaign['spend'] / manual_conversions if manual_conversions > 0 else 0
        props["평균 CPA"] = {"number": round(cpa, 2)}

    return props


def _text(content, bold=False, color="default"):
    """Notion rich_text 헬퍼"""
    t = {"type": "text", "text": {"content": content}}
    if bold or color != "default":
        t["annotations"] = {}
        if bold:
            t["annotations"]["bold"] = True
        if color != "default":
            t["annotations"]["color"] = color
    return t


def _table_row(cells):
    """테이블 행 블록 헬퍼"""
    return {
        "object": "block",
        "type": "table_row",
        "table_row": {"cells": [[_text(c)] for c in cells]}
    }


def _heading(level, text):
    """헤딩 블록 헬퍼"""
    key = f"heading_{level}"
    return {
        "object": "block",
        "type": key,
        key: {"rich_text": [_text(text)]}
    }


def create_campaign_content_blocks(campaign, manual_conversions=None):
    """캠페인 페이지 본문 블록 생성

    manual_conversions: 수동 입력된 전환수 (None이면 전환/CPA 행 생략)
    """
    blocks = []

    # ── 성과 요약 테이블 ──
    blocks.append(_heading(2, "📊 성과 요약"))

    metrics = [
        ("지출", f"${campaign['spend']:,.2f}"),
        ("노출", f"{campaign['impressions']:,}회"),
        ("클릭", f"{campaign['clicks']:,}회"),
        ("도달", f"{campaign['reach']:,}명"),
        ("CPC", f"${campaign['cpc']:.2f}"),
        ("CTR", f"{campaign['ctr']:.2f}%"),
        ("CPM", f"${campaign['cpm']:.2f}"),
    ]

    # 수동 전환수가 있으면 전환/CPA 표시
    if manual_conversions is not None:
        cpa = campaign['spend'] / manual_conversions if manual_conversions > 0 else 0
        metrics.append(("전환", f"{manual_conversions}건"))
        metrics.append(("CPA", f"${cpa:,.2f}"))
        # 인사이트에서 사용할 수 있도록 campaign에 임시 저장
        campaign['_manual_conversions'] = manual_conversions
        campaign['_manual_cpa'] = round(cpa, 2)

    header_row = {
        "object": "block",
        "type": "table_row",
        "table_row": {"cells": [[_text("메트릭", bold=True)], [_text("값", bold=True)]]}
    }
    metric_rows = [header_row] + [_table_row([m, v]) for m, v in metrics]

    blocks.append({
        "object": "block",
        "type": "table",
        "table": {
            "table_width": 2,
            "has_column_header": True,
            "has_row_header": False,
            "children": metric_rows
        }
    })

    # ── 오디언스 인사이트 ──
    audience = campaign.get('audience', {})

    if audience.get('age'):
        blocks.append(_heading(2, "👥 연령대별 분석"))
        age_header = {
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": [
                [_text("연령대", bold=True)], [_text("지출", bold=True)],
                [_text("노출", bold=True)], [_text("클릭", bold=True)]
            ]}
        }
        age_rows = [age_header] + [
            _table_row([s['age'], f"${s['spend']:,.2f}", f"{s['impressions']:,}", f"{s['clicks']:,}"])
            for s in audience['age']
        ]
        blocks.append({
            "object": "block", "type": "table",
            "table": {"table_width": 4, "has_column_header": True, "has_row_header": False, "children": age_rows}
        })

    if audience.get('gender'):
        blocks.append(_heading(2, "🚻 성별 분석"))
        gender_map = {"male": "남성", "female": "여성", "unknown": "미분류"}
        g_header = {
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": [
                [_text("성별", bold=True)], [_text("지출", bold=True)],
                [_text("노출", bold=True)], [_text("클릭", bold=True)]
            ]}
        }
        g_rows = [g_header] + [
            _table_row([gender_map.get(s['gender'], s['gender']), f"${s['spend']:,.2f}", f"{s['impressions']:,}", f"{s['clicks']:,}"])
            for s in audience['gender']
        ]
        blocks.append({
            "object": "block", "type": "table",
            "table": {"table_width": 4, "has_column_header": True, "has_row_header": False, "children": g_rows}
        })

    if audience.get('region'):
        blocks.append(_heading(2, "📍 지역별 분석"))
        r_header = {
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": [
                [_text("지역", bold=True)], [_text("지출", bold=True)],
                [_text("노출", bold=True)], [_text("클릭", bold=True)]
            ]}
        }
        r_rows = [r_header] + [
            _table_row([s['region'], f"${s['spend']:,.2f}", f"{s['impressions']:,}", f"{s['clicks']:,}"])
            for s in audience['region'][:10]  # 상위 10개 지역
        ]
        blocks.append({
            "object": "block", "type": "table",
            "table": {"table_width": 4, "has_column_header": True, "has_row_header": False, "children": r_rows}
        })

    # ── AdSet별 성과 ──
    blocks.extend(create_adset_blocks(campaign.get('adsets', [])))

    # ── 소재별 성과 ──
    blocks.extend(create_ad_blocks(campaign.get('ads', [])))

    # ── 인사이트 & 액션 플랜 ──
    blocks.extend(create_campaign_insights_blocks(campaign))

    return blocks


def create_adset_blocks(adsets):
    """AdSet별 성과 테이블 블록 생성"""
    if not adsets:
        return []

    blocks = [_heading(2, "📋 AdSet별 성과")]

    header = {
        "object": "block",
        "type": "table_row",
        "table_row": {"cells": [
            [_text("AdSet", bold=True)], [_text("지출", bold=True)],
            [_text("노출", bold=True)], [_text("클릭", bold=True)],
            [_text("CPC", bold=True)], [_text("CTR", bold=True)],
            [_text("전환", bold=True)],
        ]}
    }
    rows = [header]
    for a in adsets:
        rows.append(_table_row([
            a['adset_name'],
            f"${a['spend']:,.2f}",
            f"{a['impressions']:,}",
            f"{a['clicks']:,}",
            f"${a['cpc']:.2f}",
            f"{a['ctr']:.2f}%",
            str(a.get('conversions', 0)),
        ]))

    blocks.append({
        "object": "block", "type": "table",
        "table": {"table_width": 7, "has_column_header": True, "has_row_header": False, "children": rows}
    })
    return blocks


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


def create_campaign_insights_blocks(campaign):
    """캠페인 데이터 기반 인사이트 블록 생성 (현상 → So What → 액션)"""
    blocks = [_heading(2, "💡 주요 인사이트 & 액션 플랜")]

    audience = campaign.get('audience', {})
    spend = campaign['spend']
    insights = []

    # 1. CTR 분석
    ctr = campaign['ctr']
    if ctr > 5:
        insights.append({
            "현상": f"CTR {ctr:.2f}%로 업계 평균(2-3%)을 크게 상회",
            "So What": "광고 크리에이티브와 타겟팅이 오디언스에게 매우 효과적으로 작용하고 있음",
            "액션": "현재 크리에이티브 형식을 템플릿화하여 다른 캠페인에 적용. 예산 증액을 고려하여 도달 범위 확대"
        })
    elif ctr < 1:
        insights.append({
            "현상": f"CTR {ctr:.2f}%로 업계 평균(2-3%)에 미달",
            "So What": "광고 소재가 타겟 오디언스의 관심을 끌지 못하고 있음",
            "액션": "A/B 테스트를 통한 새로운 크리에이티브 시도. 카피 메시지와 이미지/영상 변경 필요"
        })
    else:
        insights.append({
            "현상": f"CTR {ctr:.2f}%로 업계 평균(2-3%) 수준",
            "So What": "안정적인 클릭률이지만 개선 여지 있음",
            "액션": "상위 성과 소재 분석 후 베스트 요소 결합한 신규 소재 테스트"
        })

    # 2. CPA 분석 (수동 전환수 기반)
    total_conversions = campaign.get('_manual_conversions')
    cpa = campaign.get('_manual_cpa', 0)
    if total_conversions is not None:
        if cpa > 100 and total_conversions > 0:
            insights.append({
                "현상": f"CPA ${cpa:,.2f}로 고비용 전환 구조",
                "So What": "전환당 비용이 높아 ROI 개선 필요. 스케일업 시 수익성 악화 우려",
                "액션": "랜딩 페이지 전환율 최적화(CRO). 폼 간소화, 가치 제안 강화, 로딩 속도 개선"
            })
        elif total_conversions == 0:
            insights.append({
                "현상": "해당 기간 전환 미발생",
                "So What": "클릭은 발생하나 실제 액션으로 이어지지 않음. 랜딩 페이지-광고 메시지 불일치 가능성",
                "액션": "랜딩 페이지 UX 점검. 문의 폼 위치, CTA 명확성, 모바일 최적화 개선. 리타겟팅 캠페인 추가 고려"
            })

    # 3. 연령대 분석
    age_segments = sorted(audience.get('age', []), key=lambda x: x['spend'], reverse=True)
    if age_segments and spend > 0:
        top_age = age_segments[0]
        concentration = top_age['spend'] / spend * 100
        insights.append({
            "현상": f"{top_age['age']}세 연령대가 지출의 {concentration:.1f}% 차지 (${top_age['spend']:,.2f})",
            "So What": "해당 세그먼트가 핵심 타겟으로 검증됨",
            "액션": f"{top_age['age']}세 맞춤 메시지 강화. 관심사/페인포인트 기반 크리에이티브 제작. Lookalike 확장"
        })

    # 4. 성별 분석
    gender_segments = audience.get('gender', [])
    if len(gender_segments) >= 2:
        male = next((s for s in gender_segments if s['gender'] == 'male'), None)
        female = next((s for s in gender_segments if s['gender'] == 'female'), None)
        if male and female and max(male['spend'], female['spend']) > 0:
            diff_pct = abs(male['spend'] - female['spend']) / max(male['spend'], female['spend']) * 100
            if diff_pct > 30:
                dominant = "남성" if male['spend'] > female['spend'] else "여성"
                dominant_spend = max(male['spend'], female['spend'])
                insights.append({
                    "현상": f"{dominant} 지출 ${dominant_spend:,.2f}로 성별 간 {diff_pct:.0f}% 차이",
                    "So What": f"{dominant}이 주요 고객층. 반대 성별 시장 잠재력 미개척",
                    "액션": "저성과 성별 타겟 별도 캠페인 테스트. 성별 맞춤 메시지와 비주얼로 시장 확대. 소액 예산으로 검증"
                })

    # 5. 지역 집중도 분석
    region_segments = sorted(audience.get('region', []), key=lambda x: x['spend'], reverse=True)
    if region_segments and spend > 0:
        top_region = region_segments[0]
        concentration = top_region['spend'] / spend * 100
        if concentration > 50:
            second_region = region_segments[1]['region'] if len(region_segments) > 1 else '기타'
            insights.append({
                "현상": f"{top_region['region']} 지역이 전체 지출의 {concentration:.1f}% 차지 (${top_region['spend']:,.2f})",
                "So What": "특정 지역 의존도 높음. 지역 다변화 필요",
                "액션": f"2순위 지역({second_region}) 예산 증액 테스트. 지역별 맞춤 메시지 적용"
            })

    # 인사이트를 토글 블록으로 추가
    for i, insight in enumerate(insights, 1):
        title_text = insight['현상'][:60]
        if len(insight['현상']) > 60:
            title_text += "..."
        blocks.append({
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": [_text(f"인사이트 {i}: {title_text}", bold=True)],
                "children": [
                    {
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "icon": {"emoji": "📊"},
                            "rich_text": [
                                _text("현상\n", bold=True, color="blue"),
                                _text(insight['현상'])
                            ]
                        }
                    },
                    {
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "icon": {"emoji": "🤔"},
                            "rich_text": [
                                _text("So What?\n", bold=True, color="purple"),
                                _text(insight['So What'])
                            ]
                        }
                    },
                    {
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "icon": {"emoji": "🎯"},
                            "rich_text": [
                                _text("액션 플랜\n", bold=True, color="orange"),
                                _text(insight['액션'])
                            ]
                        }
                    }
                ]
            }
        })

    return blocks


def check_existing_report(notion, database_id, week_title, date_start=None):
    """같은 캠페인+주차의 기존 리포트가 있는지 확인"""
    if date_start:
        filter_cond = {
            "and": [
                {"property": "리포트 제목", "title": {"equals": week_title}},
                {"property": "기간", "date": {"equals": date_start}},
            ]
        }
    else:
        filter_cond = {
            "property": "리포트 제목",
            "title": {"equals": week_title}
        }

    query_result = notion.databases.query(
        database_id=database_id,
        filter=filter_cond
    )
    results = query_result.get('results', [])
    return results[0]['id'] if results else None


def _clear_page_blocks(notion, page_id):
    """페이지의 기존 콘텐츠 블록 전부 삭제"""
    children = notion.blocks.children.list(block_id=page_id)
    for block in children.get("results", []):
        notion.blocks.delete(block_id=block["id"])


def _read_manual_conversions(notion, page_id):
    """기존 페이지에서 수동 입력된 총 전환수를 읽어옴"""
    page = notion.pages.retrieve(page_id=page_id)
    conv_prop = page.get("properties", {}).get("총 전환수", {})
    return conv_prop.get("number")


def create_or_update_campaign_page(notion, database_id, campaign, date_range):
    """캠페인별 Notion 페이지 생성 또는 업데이트"""
    week_title = campaign['campaign_name'].replace("새 ", "").replace(" 캠페인", "")
    date_start = date_range.get('since')
    existing_page_id = check_existing_report(notion, database_id, week_title, date_start)

    if existing_page_id:
        # 기존 페이지 → 수동 입력 전환수 보존
        conversions = _read_manual_conversions(notion, existing_page_id)
        properties = create_campaign_page_properties(campaign, date_range, conversions)
        children = create_campaign_content_blocks(campaign, conversions)

        print(f"   📝 기존 리포트 업데이트: {week_title} (전환={conversions})")
        notion.pages.update(page_id=existing_page_id, properties=properties)
        _clear_page_blocks(notion, existing_page_id)
        notion.blocks.children.append(block_id=existing_page_id, children=children)
        page_url = f"https://www.notion.so/{existing_page_id.replace('-', '')}"
    else:
        # 새 페이지 → API 전환 데이터 사용
        api_conversions = campaign['conversions']['total']
        properties = create_campaign_page_properties(campaign, date_range, api_conversions)
        # 새 페이지에는 총 전환수도 기록
        properties["총 전환수"] = {"number": api_conversions}
        children = create_campaign_content_blocks(campaign, api_conversions)

        print(f"   📝 새 리포트 생성: {week_title} (전환={api_conversions})")
        page = notion.pages.create(
            parent={"database_id": database_id},
            properties=properties,
            children=children
        )
        page_url = page['url']

    return page_url


def main():
    """메인 실행 함수"""
    try:
        print("=" * 60)
        print("Notion 리포트 업데이트 시작")
        print("=" * 60)

        # Notion API 초기화
        notion_token = os.getenv('NOTION_TOKEN')
        if not notion_token:
            raise ValueError("NOTION_TOKEN이 .env에 설정되어야 합니다.")

        notion = Client(auth=notion_token)
        print("✅ Notion API 인증 완료")

        # Database ID 로드
        database_id = load_config()
        print(f"📊 Database ID: {database_id}")

        # DB 속성 확인
        ensure_campaign_property(notion, database_id)

        # 처리된 데이터 로드
        data = get_latest_processed_data()
        date_range = data['date_range']
        campaigns = data['campaigns']

        print(f"📈 {len(campaigns)}개 캠페인 리포트 생성 중...")

        # 캠페인별 페이지 생성
        page_urls = []
        for campaign in campaigns:
            url = create_or_update_campaign_page(notion, database_id, campaign, date_range)
            page_urls.append(url)

        print("=" * 60)
        print(f"✅ Notion 리포트 업데이트 완료! ({len(page_urls)}개 캠페인)")
        for url in page_urls:
            print(f"   {url}")
        print("=" * 60)

        return page_urls[0] if page_urls else None

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
