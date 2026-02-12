#!/usr/bin/env python3
"""
Notion 데이터베이스 생성 스크립트 (최초 1회 실행)

Meta Ads Weekly Reports 데이터베이스를 생성하고
config.json에 database_id를 저장합니다.
"""

import os
import sys
import json
from dotenv import load_dotenv
from notion_client import Client

# 프로젝트 루트 디렉토리
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 환경 변수 로드
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))


def create_database(notion, parent_page_id):
    """Notion 데이터베이스 생성"""
    print("📝 Notion 데이터베이스 생성 중...")

    # 데이터베이스 속성 정의
    properties = {
        "리포트 제목": {
            "title": {}
        },
        "주차": {
            "date": {}
        },
        "총 지출": {
            "number": {
                "format": "won"
            }
        },
        "총 노출": {
            "number": {
                "format": "number_with_commas"
            }
        },
        "총 클릭": {
            "number": {
                "format": "number_with_commas"
            }
        },
        "평균 CPC": {
            "number": {
                "format": "won"
            }
        },
        "평균 CTR": {
            "number": {
                "format": "percent"
            }
        },
        "총 전환수": {
            "number": {
                "format": "number_with_commas"
            }
        },
        "평균 CPA": {
            "number": {
                "format": "won"
            }
        },
        "ROAS": {
            "number": {
                "format": "number"
            }
        },
        "캠페인 수": {
            "number": {
                "format": "number"
            }
        },
        "상태": {
            "select": {
                "options": [
                    {
                        "name": "완료",
                        "color": "green"
                    },
                    {
                        "name": "진행중",
                        "color": "yellow"
                    },
                    {
                        "name": "검토필요",
                        "color": "red"
                    }
                ]
            }
        }
    }

    # 데이터베이스 생성
    database = notion.databases.create(
        parent={
            "type": "page_id",
            "page_id": parent_page_id
        },
        title=[
            {
                "type": "text",
                "text": {
                    "content": "Meta Ads Weekly Reports"
                }
            }
        ],
        properties=properties
    )

    database_id = database['id']
    database_url = database['url']

    print(f"   ✅ 데이터베이스 생성 완료!")
    print(f"      ID: {database_id}")
    print(f"      URL: {database_url}")

    return database_id, database_url


def save_config(database_id, database_url):
    """config.json에 database_id 저장"""
    config_dir = os.path.join(PROJECT_ROOT, 'config')
    os.makedirs(config_dir, exist_ok=True)

    config_path = os.path.join(config_dir, 'config.json')

    config = {
        'notion_database_id': database_id,
        'notion_database_url': database_url,
        'created_at': os.popen('date -u +"%Y-%m-%dT%H:%M:%SZ"').read().strip()
    }

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"💾 설정 저장: {config_path}")
    return config_path


def main():
    """메인 실행 함수"""
    try:
        print("=" * 60)
        print("Notion 데이터베이스 초기 설정")
        print("=" * 60)

        # Notion API 초기화
        notion_token = os.getenv('NOTION_TOKEN')
        if not notion_token:
            raise ValueError("NOTION_TOKEN이 .env에 설정되어야 합니다.")

        notion = Client(auth=notion_token)
        print("✅ Notion API 인증 완료")

        # Parent Page ID
        parent_page_id = os.getenv('NOTION_PARENT_PAGE_ID')
        if not parent_page_id:
            raise ValueError("NOTION_PARENT_PAGE_ID가 .env에 설정되어야 합니다.")

        print(f"📄 Parent Page ID: {parent_page_id}")

        # 데이터베이스 생성
        database_id, database_url = create_database(notion, parent_page_id)

        # 설정 저장
        config_path = save_config(database_id, database_url)

        print("=" * 60)
        print("✅ 초기 설정 완료!")
        print()
        print("다음 단계:")
        print("1. GitHub Secrets에 NOTION_DATABASE_ID 추가:")
        print(f"   {database_id}")
        print()
        print("2. 데이터베이스 확인:")
        print(f"   {database_url}")
        print()
        print("3. 이제 send_to_notion.py를 실행할 수 있습니다.")
        print("=" * 60)

        return database_id

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
