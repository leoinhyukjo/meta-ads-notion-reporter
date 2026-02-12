#!/usr/bin/env python3
"""
Notion 문의 데이터 수집 스크립트

홈페이지 문의 데이터를 Notion에서 가져와 실제 전환 수를 계산합니다.
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client

# 프로젝트 루트 디렉토리
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 환경 변수 로드
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))


def fetch_leads_from_notion(date_range):
    """Notion에서 문의 데이터 수집"""
    notion_token = os.getenv('NOTION_TOKEN')
    leads_db_id = os.getenv('NOTION_LEADS_DATABASE_ID')

    if not notion_token:
        raise ValueError("NOTION_TOKEN이 .env에 설정되어야 합니다.")

    if not leads_db_id:
        raise ValueError("NOTION_LEADS_DATABASE_ID가 .env에 설정되어야 합니다.")

    notion = Client(auth=notion_token)

    print(f"📊 Notion 문의 데이터 수집 중... ({date_range['since']} ~ {date_range['until']})")

    # 날짜 범위로 필터링
    # Created At이 date_range 내에 있는 것만
    start_datetime = f"{date_range['since']}T00:00:00Z"
    end_datetime = f"{date_range['until']}T23:59:59Z"

    filter_params = {
        "and": [
            {
                "property": "Created At",
                "created_time": {
                    "on_or_after": start_datetime
                }
            },
            {
                "property": "Created At",
                "created_time": {
                    "on_or_before": end_datetime
                }
            }
        ]
    }

    # 데이터베이스 쿼리
    results = []
    has_more = True
    next_cursor = None

    while has_more:
        response = notion.databases.query(
            database_id=leads_db_id,
            filter=filter_params,
            start_cursor=next_cursor
        )

        results.extend(response.get('results', []))
        has_more = response.get('has_more', False)
        next_cursor = response.get('next_cursor')

    # 데이터 추출
    leads = []
    for page in results:
        props = page['properties']

        # 이름 추출
        name = ''
        if props.get('Name', {}).get('title'):
            name = props['Name']['title'][0]['text']['content']

        # 회사명 추출
        company = ''
        if props.get('Company', {}).get('rich_text'):
            company = props['Company']['rich_text'][0]['text']['content']

        # 이메일 추출
        email = props.get('Email', {}).get('email', '')

        # 생성 시간 추출
        created_at = props.get('Created At', {}).get('created_time', '')

        leads.append({
            'name': name,
            'company': company,
            'email': email,
            'created_at': created_at,
            'page_id': page['id']
        })

    print(f"   ✅ {len(leads)}개 문의 수집 완료")

    return leads


def save_leads_data(leads, date_range):
    """문의 데이터를 JSON 파일로 저장"""
    output_path = os.path.join(
        PROJECT_ROOT,
        'data',
        'raw',
        f"notion_leads_{datetime.now().strftime('%Y-%m-%d')}.json"
    )

    data = {
        'collected_at': datetime.now().isoformat(),
        'date_range': date_range,
        'total_leads': len(leads),
        'leads': leads
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"💾 문의 데이터 저장: {output_path}")
    return output_path


def main(date_range):
    """메인 실행 함수"""
    try:
        print("=" * 60)
        print("Notion 문의 데이터 수집 시작")
        print("=" * 60)

        # 문의 데이터 수집
        leads = fetch_leads_from_notion(date_range)

        # 저장
        output_path = save_leads_data(leads, date_range)

        print("=" * 60)
        print("✅ 문의 데이터 수집 완료!")
        print(f"   총 문의 수: {len(leads)}개")
        print(f"   파일 경로: {output_path}")
        print("=" * 60)

        return output_path, len(leads)

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # 테스트용 날짜 범위
    from datetime import date, timedelta
    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    date_range = {
        'since': start_date.strftime('%Y-%m-%d'),
        'until': end_date.strftime('%Y-%m-%d')
    }

    main(date_range)
