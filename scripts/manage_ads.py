#!/usr/bin/env python3
"""
Meta 광고 관리 스크립트 (on/off)

캠페인·광고세트·광고 단위로 상태를 조회하고 켜기/끄기를 수행합니다.

사용법:
  python manage_ads.py list                          # 캠페인 목록 + 상태 조회
  python manage_ads.py list --level adset            # 광고세트 목록
  python manage_ads.py list --level ad               # 개별 광고 목록
  python manage_ads.py pause <ID>                    # 일시정지
  python manage_ads.py activate <ID>                 # 활성화
  python manage_ads.py pause <ID1> <ID2> ...         # 여러 개 동시 제어
"""

import os
import sys
import argparse
from pathlib import Path

# ── 프로젝트 설정 ──────────────────────────────────────────────
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, PROJECT_ROOT)

# .env 수동 파싱 (기존 프로젝트 패턴 유지)
_dotenv_path = os.path.join(PROJECT_ROOT, '.env')
if os.path.isfile(_dotenv_path):
    with open(_dotenv_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith('#') or '=' not in _line:
                continue
            _key, _, _val = _line.partition('=')
            _key = _key.strip()
            _val = _val.strip().strip('"').strip("'")
            if _key and _key not in os.environ:
                os.environ[_key] = _val

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=True)

# ── 상수 ──────────────────────────────────────────────────────
API_VERSION = 'v19.0'
BASE_URL = f'https://graph.facebook.com/{API_VERSION}'
ACCESS_TOKEN = os.getenv('META_ACCESS_TOKEN')
AD_ACCOUNT_ID = os.getenv('META_AD_ACCOUNT_ID')

STATUS_DISPLAY = {
    'ACTIVE': '🟢 활성',
    'PAUSED': '⏸️  일시정지',
    'CAMPAIGN_PAUSED': '⏸️  캠페인정지',
    'ADSET_PAUSED': '⏸️  광고세트정지',
    'DELETED': '🗑️  삭제됨',
    'ARCHIVED': '📦 보관됨',
}

LEVEL_EDGE = {
    'campaign': 'campaigns',
    'adset': 'adsets',
    'ad': 'ads',
}


def _check_config():
    if not ACCESS_TOKEN:
        print("❌ META_ACCESS_TOKEN이 .env에 설정되어야 합니다.")
        sys.exit(1)
    if not AD_ACCOUNT_ID:
        print("❌ META_AD_ACCOUNT_ID가 .env에 설정되어야 합니다.")
        sys.exit(1)


# ── 조회 ──────────────────────────────────────────────────────
def list_objects(level: str):
    """캠페인/광고세트/광고 목록 조회"""
    edge = LEVEL_EDGE[level]
    url = f'{BASE_URL}/{AD_ACCOUNT_ID}/{edge}'
    params = {
        'access_token': ACCESS_TOKEN,
        'fields': 'id,name,status,effective_status',
        'limit': 100,
    }

    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        print(f"❌ API 에러: {resp.status_code} - {resp.text}")
        sys.exit(1)

    items = resp.json().get('data', [])
    if not items:
        print(f"조회된 {level}이(가) 없습니다.")
        return

    # 상태별 정렬 (ACTIVE 먼저)
    order = {'ACTIVE': 0, 'PAUSED': 1}
    items.sort(key=lambda x: order.get(x.get('effective_status', ''), 9))

    print(f"\n{'=' * 70}")
    print(f"  {level.upper()} 목록  ({len(items)}개)")
    print(f"{'=' * 70}")
    print(f"  {'상태':<14} {'ID':<22} 이름")
    print(f"  {'-' * 14} {'-' * 22} {'-' * 30}")

    for item in items:
        status = item.get('effective_status', 'UNKNOWN')
        display = STATUS_DISPLAY.get(status, f'❓ {status}')
        print(f"  {display:<14} {item['id']:<22} {item['name']}")

    print()


# ── 상태 변경 ─────────────────────────────────────────────────
def update_status(object_ids: list[str], new_status: str):
    """광고 객체 상태 변경 (ACTIVE / PAUSED)"""
    action = '활성화' if new_status == 'ACTIVE' else '일시정지'
    print(f"\n{len(object_ids)}개 객체 {action} 중...\n")

    success, fail = 0, 0
    for obj_id in object_ids:
        url = f'{BASE_URL}/{obj_id}'
        params = {
            'access_token': ACCESS_TOKEN,
            'status': new_status,
        }
        resp = requests.post(url, params=params)

        if resp.status_code == 200 and resp.json().get('success'):
            emoji = '🟢' if new_status == 'ACTIVE' else '⏸️ '
            print(f"  {emoji} {obj_id} → {action} 완료")
            success += 1
        else:
            print(f"  ❌ {obj_id} → 실패: {resp.text}")
            fail += 1

    print(f"\n결과: 성공 {success}개 / 실패 {fail}개")


# ── CLI ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='Meta 광고 관리 (on/off)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python manage_ads.py list                     캠페인 목록 조회
  python manage_ads.py list --level adset       광고세트 목록 조회
  python manage_ads.py pause 12345678           캠페인 일시정지
  python manage_ads.py activate 12345678        캠페인 활성화
  python manage_ads.py pause 111 222 333        여러 개 동시 정지
        """,
    )
    sub = parser.add_subparsers(dest='command')

    # list
    p_list = sub.add_parser('list', help='캠페인/광고세트/광고 목록 조회')
    p_list.add_argument('--level', choices=['campaign', 'adset', 'ad'], default='campaign')

    # pause
    p_pause = sub.add_parser('pause', help='일시정지')
    p_pause.add_argument('ids', nargs='+', help='대상 ID (복수 가능)')

    # activate
    p_activate = sub.add_parser('activate', help='활성화')
    p_activate.add_argument('ids', nargs='+', help='대상 ID (복수 가능)')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    _check_config()

    if args.command == 'list':
        list_objects(args.level)
    elif args.command == 'pause':
        update_status(args.ids, 'PAUSED')
    elif args.command == 'activate':
        update_status(args.ids, 'ACTIVE')


if __name__ == '__main__':
    main()
