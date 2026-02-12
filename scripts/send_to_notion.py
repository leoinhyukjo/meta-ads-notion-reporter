#!/usr/bin/env python3
"""
Notion 리포트 업데이트 스크립트

처리된 데이터를 Notion 데이터베이스에 주간 리포트 페이지로 생성합니다.
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


def create_page_properties(data):
    """Notion 페이지 속성 생성"""
    summary = data['summary']
    date_range = data['date_range']

    # 주차 제목
    week_title = f"Week of {date_range['since']}"

    properties = {
        "리포트 제목": {
            "title": [
                {
                    "text": {
                        "content": week_title
                    }
                }
            ]
        },
        "주차": {
            "date": {
                "start": date_range['since'],
                "end": date_range['until']
            }
        },
        "총 지출": {
            "number": summary['total_spend']
        },
        "총 노출": {
            "number": summary['total_impressions']
        },
        "총 클릭": {
            "number": summary['total_clicks']
        },
        "평균 CPC": {
            "number": summary['avg_cpc']
        },
        "평균 CTR": {
            "number": summary['avg_ctr'] / 100  # Notion percent format은 0-1 범위
        },
        "총 전환수": {
            "number": summary['total_conversions']
        },
        "평균 CPA": {
            "number": summary['avg_cpa']
        },
        "ROAS": {
            "number": summary['roas']
        },
        "캠페인 수": {
            "number": summary['campaign_count']
        },
        "상태": {
            "select": {
                "name": "완료"
            }
        }
    }

    return properties


def create_summary_blocks(summary):
    """주간 요약 섹션 블록 생성"""
    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "주간 요약"}
                    }
                ]
            }
        },
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"emoji": "💰"},
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"총 지출: {summary['total_spend']:,.0f}원\n"
                                      f"총 노출: {summary['total_impressions']:,}회\n"
                                      f"총 클릭: {summary['total_clicks']:,}회\n"
                                      f"평균 CPC: {summary['avg_cpc']:,.0f}원\n"
                                      f"평균 CTR: {summary['avg_ctr']:.2f}%\n"
                                      f"총 전환: {summary['total_conversions']:,}개\n"
                                      f"평균 CPA: {summary['avg_cpa']:,.0f}원\n"
                                      f"ROAS: {summary['roas']:.2f}"
                        }
                    }
                ]
            }
        }
    ]

    return blocks


def create_campaign_table_blocks(campaigns):
    """캠페인별 성과 테이블 블록 생성"""
    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "캠페인별 성과"}
                    }
                ]
            }
        }
    ]

    # 상위 10개 캠페인만 표시
    top_campaigns = campaigns[:10]

    for campaign in top_campaigns:
        campaign_block = {
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"{campaign['campaign_name']} | "
                                      f"지출: {campaign['spend']:,.0f}원 | "
                                      f"ROAS: {campaign['roas']:.2f}"
                        }
                    }
                ],
                "children": [
                    {
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": f"노출: {campaign['impressions']:,}회 | "
                                                  f"클릭: {campaign['clicks']:,}회 | "
                                                  f"CTR: {campaign['ctr']:.2f}%"
                                    }
                                }
                            ]
                        }
                    },
                    {
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": f"CPC: {campaign['cpc']:,.0f}원 | "
                                                  f"전환: {campaign['conversions']['total']}개 | "
                                                  f"CPA: {campaign['cpa']:,.0f}원"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
        blocks.append(campaign_block)

    return blocks


def create_audience_blocks(audience):
    """오디언스 인사이트 블록 생성"""
    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "오디언스 인사이트"}
                    }
                ]
            }
        }
    ]

    # 연령대별
    blocks.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": "연령대별 분석"}
                }
            ]
        }
    })

    for segment in audience['age'][:5]:  # 상위 5개만
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"{segment['age']}세: "
                                      f"지출 {segment['spend']:,.0f}원 | "
                                      f"노출 {segment['impressions']:,}회 | "
                                      f"클릭 {segment['clicks']:,}회"
                        }
                    }
                ]
            }
        })

    # 성별
    blocks.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": "성별 분석"}
                }
            ]
        }
    })

    for segment in audience['gender']:
        gender_label = {"male": "남성", "female": "여성", "unknown": "미분류"}.get(
            segment['gender'], segment['gender']
        )
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"{gender_label}: "
                                      f"지출 {segment['spend']:,.0f}원 | "
                                      f"노출 {segment['impressions']:,}회 | "
                                      f"클릭 {segment['clicks']:,}회"
                        }
                    }
                ]
            }
        })

    # 지역별
    blocks.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": "지역별 분석 (Top 5)"}
                }
            ]
        }
    })

    for segment in audience['region'][:5]:  # 상위 5개만
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"{segment['region']}: "
                                      f"지출 {segment['spend']:,.0f}원 | "
                                      f"노출 {segment['impressions']:,}회 | "
                                      f"클릭 {segment['clicks']:,}회"
                        }
                    }
                ]
            }
        })

    return blocks


def create_page_content(data):
    """Notion 페이지 콘텐츠 블록 생성"""
    blocks = []

    # 주간 요약
    blocks.extend(create_summary_blocks(data['summary']))

    # 캠페인별 성과
    blocks.extend(create_campaign_table_blocks(data['campaigns']))

    # 오디언스 인사이트
    blocks.extend(create_audience_blocks(data['audience']))

    return blocks


def check_existing_report(notion, database_id, date_range):
    """같은 주차의 기존 리포트가 있는지 확인"""
    week_title = f"Week of {date_range['since']}"

    query_result = notion.databases.query(
        database_id=database_id,
        filter={
            "property": "리포트 제목",
            "title": {
                "equals": week_title
            }
        }
    )

    results = query_result.get('results', [])
    return results[0]['id'] if results else None


def create_or_update_page(notion, database_id, data):
    """Notion 페이지 생성 또는 업데이트"""
    properties = create_page_properties(data)
    children = create_page_content(data)

    # 기존 리포트 확인
    existing_page_id = check_existing_report(notion, database_id, data['date_range'])

    if existing_page_id:
        print(f"📝 기존 리포트 업데이트 중... (Page ID: {existing_page_id})")

        # 속성 업데이트
        notion.pages.update(page_id=existing_page_id, properties=properties)

        # 기존 블록 삭제 후 새 블록 추가
        # (Notion API 제한으로 블록 일괄 삭제는 수동으로 처리 필요)
        print("   ⚠️  기존 콘텐츠는 수동으로 삭제하고 새 콘텐츠를 추가합니다.")

        # 새 블록 추가
        notion.blocks.children.append(block_id=existing_page_id, children=children)

        page_url = f"https://www.notion.so/{existing_page_id.replace('-', '')}"
        print(f"   ✅ 리포트 업데이트 완료: {page_url}")

        return existing_page_id, page_url

    else:
        print("📝 새 리포트 페이지 생성 중...")

        # 새 페이지 생성
        page = notion.pages.create(
            parent={"database_id": database_id},
            properties=properties,
            children=children
        )

        page_id = page['id']
        page_url = page['url']

        print(f"   ✅ 리포트 생성 완료: {page_url}")

        return page_id, page_url


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

        # 처리된 데이터 로드
        data = get_latest_processed_data()

        # Notion 페이지 생성/업데이트
        page_id, page_url = create_or_update_page(notion, database_id, data)

        print("=" * 60)
        print("✅ Notion 리포트 업데이트 완료!")
        print(f"   Page ID: {page_id}")
        print(f"   URL: {page_url}")
        print("=" * 60)

        return page_url

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
