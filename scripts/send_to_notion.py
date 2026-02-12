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
    """주간 요약 섹션 블록 생성 (테이블 형식)"""
    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "📊 주간 요약"}
                    }
                ]
            }
        },
        {
            "object": "block",
            "type": "table",
            "table": {
                "table_width": 2,
                "has_column_header": True,
                "has_row_header": False,
                "children": [
                    {
                        "object": "block",
                        "type": "table_row",
                        "table_row": {
                            "cells": [
                                [{"type": "text", "text": {"content": "메트릭"}, "annotations": {"bold": True}}],
                                [{"type": "text", "text": {"content": "값"}, "annotations": {"bold": True}}]
                            ]
                        }
                    },
                    {
                        "object": "block",
                        "type": "table_row",
                        "table_row": {
                            "cells": [
                                [{"type": "text", "text": {"content": "총 지출"}}],
                                [{"type": "text", "text": {"content": f"${summary['total_spend']:,.2f}"}}]
                            ]
                        }
                    },
                    {
                        "object": "block",
                        "type": "table_row",
                        "table_row": {
                            "cells": [
                                [{"type": "text", "text": {"content": "총 노출"}}],
                                [{"type": "text", "text": {"content": f"{summary['total_impressions']:,}회"}}]
                            ]
                        }
                    },
                    {
                        "object": "block",
                        "type": "table_row",
                        "table_row": {
                            "cells": [
                                [{"type": "text", "text": {"content": "총 클릭"}}],
                                [{"type": "text", "text": {"content": f"{summary['total_clicks']:,}회"}}]
                            ]
                        }
                    },
                    {
                        "object": "block",
                        "type": "table_row",
                        "table_row": {
                            "cells": [
                                [{"type": "text", "text": {"content": "평균 CPC"}}],
                                [{"type": "text", "text": {"content": f"${summary['avg_cpc']:.2f}"}}]
                            ]
                        }
                    },
                    {
                        "object": "block",
                        "type": "table_row",
                        "table_row": {
                            "cells": [
                                [{"type": "text", "text": {"content": "평균 CTR"}}],
                                [{"type": "text", "text": {"content": f"{summary['avg_ctr']:.2f}%"}}]
                            ]
                        }
                    },
                    {
                        "object": "block",
                        "type": "table_row",
                        "table_row": {
                            "cells": [
                                [{"type": "text", "text": {"content": "총 전환 (문의)"}}],
                                [{"type": "text", "text": {"content": f"{summary['total_conversions']:,}개"}}]
                            ]
                        }
                    },
                    {
                        "object": "block",
                        "type": "table_row",
                        "table_row": {
                            "cells": [
                                [{"type": "text", "text": {"content": "평균 CPA"}}],
                                [{"type": "text", "text": {"content": f"${summary['avg_cpa']:,.2f}"}}]
                            ]
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
                        "text": {"content": "📈 캠페인별 성과"}
                    }
                ]
            }
        }
    ]

    # 상위 10개 캠페인만 표시
    top_campaigns = campaigns[:10]

    # 테이블 헤더 행 생성
    table_rows = [
        {
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [
                    [{"type": "text", "text": {"content": "캠페인명"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "지출"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "노출"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "클릭"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "CPC"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "CTR"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "전환"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "CPA"}, "annotations": {"bold": True}}]
                ]
            }
        }
    ]

    # 각 캠페인 데이터 행 추가
    for campaign in top_campaigns:
        table_rows.append({
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [
                    [{"type": "text", "text": {"content": campaign['campaign_name']}}],
                    [{"type": "text", "text": {"content": f"${campaign['spend']:,.2f}"}}],
                    [{"type": "text", "text": {"content": f"{campaign['impressions']:,}"}}],
                    [{"type": "text", "text": {"content": f"{campaign['clicks']:,}"}}],
                    [{"type": "text", "text": {"content": f"${campaign['cpc']:.2f}"}}],
                    [{"type": "text", "text": {"content": f"{campaign['ctr']:.2f}%"}}],
                    [{"type": "text", "text": {"content": f"{campaign['conversions']['total']}"}}],
                    [{"type": "text", "text": {"content": f"${campaign['cpa']:,.2f}"}}]
                ]
            }
        })

    # 테이블 블록 생성
    blocks.append({
        "object": "block",
        "type": "table",
        "table": {
            "table_width": 8,
            "has_column_header": True,
            "has_row_header": False,
            "children": table_rows
        }
    })

    return blocks


def create_audience_blocks(audience):
    """오디언스 인사이트 블록 생성 (테이블 형식)"""
    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "👥 오디언스 인사이트"}
                    }
                ]
            }
        }
    ]

    # 연령대별 테이블
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

    age_rows = [
        {
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [
                    [{"type": "text", "text": {"content": "연령대"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "지출"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "노출"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "클릭"}, "annotations": {"bold": True}}]
                ]
            }
        }
    ]

    for segment in audience['age']:
        age_rows.append({
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [
                    [{"type": "text", "text": {"content": segment['age']}}],
                    [{"type": "text", "text": {"content": f"${segment['spend']:,.2f}"}}],
                    [{"type": "text", "text": {"content": f"{segment['impressions']:,}"}}],
                    [{"type": "text", "text": {"content": f"{segment['clicks']:,}"}}]
                ]
            }
        })

    blocks.append({
        "object": "block",
        "type": "table",
        "table": {
            "table_width": 4,
            "has_column_header": True,
            "has_row_header": False,
            "children": age_rows
        }
    })

    # 성별 테이블
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

    gender_rows = [
        {
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [
                    [{"type": "text", "text": {"content": "성별"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "지출"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "노출"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "클릭"}, "annotations": {"bold": True}}]
                ]
            }
        }
    ]

    for segment in audience['gender']:
        gender_label = {"male": "남성", "female": "여성", "unknown": "미분류"}.get(
            segment['gender'], segment['gender']
        )
        gender_rows.append({
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [
                    [{"type": "text", "text": {"content": gender_label}}],
                    [{"type": "text", "text": {"content": f"${segment['spend']:,.2f}"}}],
                    [{"type": "text", "text": {"content": f"{segment['impressions']:,}"}}],
                    [{"type": "text", "text": {"content": f"{segment['clicks']:,}"}}]
                ]
            }
        })

    blocks.append({
        "object": "block",
        "type": "table",
        "table": {
            "table_width": 4,
            "has_column_header": True,
            "has_row_header": False,
            "children": gender_rows
        }
    })

    # 지역별 테이블
    blocks.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": "지역별 분석"}
                }
            ]
        }
    })

    region_rows = [
        {
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [
                    [{"type": "text", "text": {"content": "지역"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "지출"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "노출"}, "annotations": {"bold": True}}],
                    [{"type": "text", "text": {"content": "클릭"}, "annotations": {"bold": True}}]
                ]
            }
        }
    ]

    for segment in audience['region']:
        region_rows.append({
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [
                    [{"type": "text", "text": {"content": segment['region']}}],
                    [{"type": "text", "text": {"content": f"${segment['spend']:,.2f}"}}],
                    [{"type": "text", "text": {"content": f"{segment['impressions']:,}"}}],
                    [{"type": "text", "text": {"content": f"{segment['clicks']:,}"}}]
                ]
            }
        })

    blocks.append({
        "object": "block",
        "type": "table",
        "table": {
            "table_width": 4,
            "has_column_header": True,
            "has_row_header": False,
            "children": region_rows
        }
    })

    return blocks


def create_insights_blocks(data):
    """데이터 기반 인사이트 블록 생성 (현상 → So What → 액션)"""
    summary = data['summary']
    audience = data['audience']
    campaigns = data['campaigns']

    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "💡 주요 인사이트 & 액션 플랜"}
                    }
                ]
            }
        }
    ]

    insights = []

    # 1. CTR 분석
    avg_ctr = summary['avg_ctr']
    if avg_ctr > 5:
        insights.append({
            "현상": f"평균 CTR {avg_ctr:.2f}%로 업계 평균(2-3%)을 크게 상회",
            "So What": "광고 크리에이티브와 타겟팅이 오디언스에게 매우 효과적으로 작용하고 있음. 높은 관심도 확보",
            "액션": "현재 크리에이티브 형식을 템플릿화하여 다른 캠페인에 적용. 예산 증액을 고려하여 도달 범위 확대"
        })
    elif avg_ctr < 1:
        insights.append({
            "현상": f"평균 CTR {avg_ctr:.2f}%로 업계 평균(2-3%)에 미달",
            "So What": "광고 소재가 타겟 오디언스의 관심을 끌지 못하고 있음",
            "액션": "A/B 테스트를 통한 새로운 크리에이티브 시도. 카피 메시지와 이미지/영상 변경 필요"
        })

    # 2. CPA 분석
    avg_cpa = summary['avg_cpa']
    total_conversions = summary['total_conversions']
    if avg_cpa > 100 and total_conversions > 0:
        insights.append({
            "현상": f"평균 CPA ${avg_cpa:,.2f}로 고비용 전환 구조",
            "So What": "전환당 비용이 높아 ROI 개선 필요. 현재 구조로는 스케일업 시 수익성 악화 우려",
            "액션": "랜딩 페이지 전환율 최적화(CRO). 폼 간소화, 가치 제안 강화, 로딩 속도 개선으로 전환율 2배 목표"
        })
    elif total_conversions == 0:
        insights.append({
            "현상": f"주간 전환 {total_conversions}건으로 전환 미발생",
            "So What": "클릭은 발생하나 실제 액션으로 이어지지 않음. 랜딩 페이지-광고 메시지 불일치 가능성",
            "액션": "랜딩 페이지 사용자 경험 점검. 문의 폼 위치, CTA 명확성, 모바일 최적화 개선. 리타겟팅 캠페인 추가 고려"
        })

    # 3. 연령대 분석
    age_segments = sorted(audience['age'], key=lambda x: x['spend'], reverse=True)
    if len(age_segments) > 0:
        top_age = age_segments[0]
        top_age_ctr = (top_age['clicks'] / top_age['impressions'] * 100) if top_age['impressions'] > 0 else 0

        insights.append({
            "현상": f"{top_age['age']}세 연령대가 지출의 {(top_age['spend']/summary['total_spend']*100):.1f}% 차지 (${top_age['spend']:,.2f})",
            "So What": f"특정 연령대에 광고비 집중. 해당 세그먼트가 핵심 타겟으로 검증됨",
            "액션": f"{top_age['age']}세 맞춤 메시지 강화. 해당 연령대 관심사/페인포인트 기반 크리에이티브 제작. 유사 오디언스(Lookalike) 확장"
        })

    # 4. 성별 분석
    gender_segments = audience['gender']
    if len(gender_segments) >= 2:
        male = next((s for s in gender_segments if s['gender'] == 'male'), None)
        female = next((s for s in gender_segments if s['gender'] == 'female'), None)

        if male and female:
            gender_diff_pct = abs(male['spend'] - female['spend']) / max(male['spend'], female['spend']) * 100
            if gender_diff_pct > 30:
                dominant_gender = "남성" if male['spend'] > female['spend'] else "여성"
                dominant_spend = max(male['spend'], female['spend'])

                insights.append({
                    "현상": f"{dominant_gender} 지출 ${dominant_spend:,.2f}로 성별 간 {gender_diff_pct:.0f}% 차이",
                    "So What": f"{dominant_gender}이 주요 고객층. 반대 성별 시장 잠재력 미개척",
                    "액션": f"저성과 성별 타겟 별도 캠페인 테스트. 성별 맞춤 메시지와 비주얼로 시장 확대 시도. 초기 소액 예산으로 검증"
                })

    # 5. 지역 집중도 분석
    region_segments = sorted(audience['region'], key=lambda x: x['spend'], reverse=True)
    if len(region_segments) > 0:
        top_region = region_segments[0]
        region_concentration = top_region['spend'] / summary['total_spend'] * 100

        if region_concentration > 50:
            insights.append({
                "현상": f"{top_region['region']} 지역이 전체 지출의 {region_concentration:.1f}% 차지 (${top_region['spend']:,.2f})",
                "So What": "특정 지역 의존도 높음. 지역 다변화 필요성",
                "액션": f"2순위 지역({region_segments[1]['region'] if len(region_segments) > 1 else '기타'}) 예산 증액 테스트. 지역별 맞춤 메시지(방언, 지역 이슈) 적용"
            })

    # 인사이트를 토글 블록으로 추가
    for i, insight in enumerate(insights, 1):
        blocks.append({
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": f"인사이트 {i}: {insight['현상'][:50]}..."},
                        "annotations": {"bold": True}
                    }
                ],
                "children": [
                    {
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "icon": {"emoji": "📊"},
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {"content": "현상\n"},
                                    "annotations": {"bold": True, "color": "blue"}
                                },
                                {
                                    "type": "text",
                                    "text": {"content": insight['현상']}
                                }
                            ]
                        }
                    },
                    {
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "icon": {"emoji": "🤔"},
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {"content": "So What?\n"},
                                    "annotations": {"bold": True, "color": "purple"}
                                },
                                {
                                    "type": "text",
                                    "text": {"content": insight['So What']}
                                }
                            ]
                        }
                    },
                    {
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "icon": {"emoji": "🎯"},
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {"content": "액션 플랜\n"},
                                    "annotations": {"bold": True, "color": "orange"}
                                },
                                {
                                    "type": "text",
                                    "text": {"content": insight['액션']}
                                }
                            ]
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

    # 데이터 기반 인사이트
    blocks.extend(create_insights_blocks(data))

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
