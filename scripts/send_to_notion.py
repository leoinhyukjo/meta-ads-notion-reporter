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


def create_campaign_page_properties(campaign, date_range):
    """캠페인별 Notion 페이지 속성 생성"""
    name = campaign['campaign_name']
    short_name = name.replace("새 ", "").replace(" 캠페인", "")
    week_title = f"Week of {date_range['since']} | {short_name}"

    impressions = campaign['impressions']
    clicks = campaign['clicks']
    spend = campaign['spend']
    cpc = campaign['cpc']
    ctr = campaign['ctr']
    conversions = campaign['conversions']['total']
    cpa = campaign['cpa']

    return {
        "리포트 제목": {
            "title": [{"text": {"content": week_title}}]
        },
        "주차": {
            "date": {"start": date_range['since'], "end": date_range['until']}
        },
        "캠페인명": {
            "select": {"name": name}
        },
        "총 지출": {"number": spend},
        "총 노출": {"number": impressions},
        "총 클릭": {"number": clicks},
        "평균 CPC": {"number": cpc},
        "평균 CTR": {"number": ctr / 100 if ctr > 1 else ctr},
        "총 전환수": {"number": conversions},
        "평균 CPA": {"number": cpa},
        "캠페인 수": {"number": 1},
        "상태": {"select": {"name": "완료"}},
    }


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


def create_campaign_content_blocks(campaign):
    """캠페인 페이지 본문 블록 생성"""
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
        ("전환", f"{campaign['conversions']['total']}건"),
        ("CPA", f"${campaign['cpa']:,.2f}"),
    ]

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

    return blocks


def check_existing_report(notion, database_id, week_title):
    """같은 캠페인+주차의 기존 리포트가 있는지 확인"""
    query_result = notion.databases.query(
        database_id=database_id,
        filter={
            "property": "리포트 제목",
            "title": {"equals": week_title}
        }
    )
    results = query_result.get('results', [])
    return results[0]['id'] if results else None


def create_or_update_campaign_page(notion, database_id, campaign, date_range):
    """캠페인별 Notion 페이지 생성 또는 업데이트"""
    properties = create_campaign_page_properties(campaign, date_range)
    children = create_campaign_content_blocks(campaign)

    week_title = properties["리포트 제목"]["title"][0]["text"]["content"]
    existing_page_id = check_existing_report(notion, database_id, week_title)

    if existing_page_id:
        print(f"   📝 기존 리포트 업데이트: {week_title}")
        notion.pages.update(page_id=existing_page_id, properties=properties)
        notion.blocks.children.append(block_id=existing_page_id, children=children)
        page_url = f"https://www.notion.so/{existing_page_id.replace('-', '')}"
    else:
        print(f"   📝 새 리포트 생성: {week_title}")
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
