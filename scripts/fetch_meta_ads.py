#!/usr/bin/env python3
"""
Meta Marketing API 데이터 수집 스크립트

지난 7일간의 Meta 광고 성과 데이터를 수집하여 JSON 파일로 저장합니다.
- 캠페인 레벨 인사이트
- 오디언스 breakdown (age, gender, region)
"""

import os
import sys
import json
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# ── Early healthcheck (stdlib only) ──────────────────────────
# Import 실패 시에도 healthcheck ping이 가능하도록 서드파티 import 전에 정의

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, PROJECT_ROOT)

# .env를 stdlib만으로 수동 파싱 (load_dotenv 없이)
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


def _ping_healthcheck(status: str = "success", body: str = ""):
    """Healthchecks.io heartbeat ping. status: 'success' | 'fail' | 'start'"""
    url = os.environ.get("HEALTHCHECK_PING_URL", "")
    if not url:
        return
    try:
        suffix = {"fail": "/fail", "start": "/start"}.get(status, "")
        req = urllib.request.Request(url + suffix, data=body.encode()[:10000] if body else None)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[WARN] Healthcheck ping 실패: {e}")


# ── Third-party imports ──────────────────────────────────────
try:
    import requests
    from dotenv import load_dotenv
except ImportError as exc:
    _ping_healthcheck("fail", f"ImportError: {exc}")
    print(f"[FATAL] 필수 패키지 import 실패: {exc}")
    raise SystemExit(1)

# 환경 변수 로드 (load_dotenv로 덮어쓰기 — 수동 파싱보다 정확)
load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=True)


def get_date_range():
    """전주 월~일 날짜 범위 반환

    실행일(월요일)을 기준으로 지난 주 월요일~일요일 기간을 반환합니다.
    예: 2026-02-17(월) 실행 → 2026-02-10(월) ~ 2026-02-16(일)
    """
    today = datetime.now().date()

    # 오늘이 무슨 요일인지 확인 (0=월요일, 6=일요일)
    weekday = today.weekday()

    # 지난 주 월요일 날짜 계산
    # 만약 오늘이 월요일이면 7일 전, 화요일이면 8일 전...
    days_to_last_monday = weekday + 7
    last_monday = today - timedelta(days=days_to_last_monday)

    # 지난 주 일요일은 지난 주 월요일 + 6일
    last_sunday = last_monday + timedelta(days=6)

    return {
        'since': last_monday.strftime('%Y-%m-%d'),
        'until': last_sunday.strftime('%Y-%m-%d')
    }


def get_access_token():
    """Access Token 확인"""
    access_token = os.getenv('META_ACCESS_TOKEN')

    if not access_token:
        raise ValueError("META_ACCESS_TOKEN이 .env에 설정되어야 합니다.")

    print("✅ Meta API Access Token 확인 완료")
    return access_token


def fetch_campaign_insights(ad_account_id, date_range, access_token):
    """캠페인별 성과 데이터 수집"""
    api_version = 'v19.0'
    base_url = f'https://graph.facebook.com/{api_version}'

    # 수집할 필드
    fields = [
        'campaign_id',
        'campaign_name',
        'impressions',
        'clicks',
        'spend',
        'reach',
        'frequency',
        'cpc',
        'cpm',
        'cpp',
        'ctr',
        'actions',
        'action_values',
        'cost_per_action_type',
    ]

    # API 요청 파라미터
    params = {
        'access_token': access_token,
        'fields': ','.join(fields),
        'time_range': json.dumps(date_range),
        'level': 'campaign',
        'limit': 500
    }

    print(f"📊 캠페인 인사이트 수집 중... ({date_range['since']} ~ {date_range['until']})")

    # API 호출
    url = f'{base_url}/{ad_account_id}/insights'
    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise Exception(f"Meta API 에러: {response.status_code} - {response.text}")

    data = response.json()
    campaign_data = data.get('data', [])

    print(f"   ✅ {len(campaign_data)}개 캠페인 데이터 수집 완료")
    return campaign_data


def fetch_audience_insights(ad_account_id, date_range, access_token):
    """오디언스 breakdown 데이터 수집"""
    api_version = 'v19.0'
    base_url = f'https://graph.facebook.com/{api_version}'

    fields = [
        'campaign_id',
        'campaign_name',
        'impressions',
        'clicks',
        'spend',
        'actions',
    ]

    audience_data = {}

    # 연령대별 분석 (캠페인별)
    print("📊 연령대별 인사이트 수집 중...")
    params = {
        'access_token': access_token,
        'fields': ','.join(fields),
        'time_range': json.dumps(date_range),
        'level': 'campaign',
        'breakdowns': 'age',
        'limit': 500
    }
    url = f'{base_url}/{ad_account_id}/insights'
    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise Exception(f"Meta API 에러 (연령대): {response.status_code} - {response.text}")

    audience_data['age'] = response.json().get('data', [])
    print(f"   ✅ {len(audience_data['age'])}개 연령대 데이터 수집 완료")

    # 성별 분석
    print("📊 성별 인사이트 수집 중...")
    params['breakdowns'] = 'gender'
    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise Exception(f"Meta API 에러 (성별): {response.status_code} - {response.text}")

    audience_data['gender'] = response.json().get('data', [])
    print(f"   ✅ {len(audience_data['gender'])}개 성별 데이터 수집 완료")

    # 지역별 분석
    print("📊 지역별 인사이트 수집 중...")
    params['breakdowns'] = 'region'
    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise Exception(f"Meta API 에러 (지역): {response.status_code} - {response.text}")

    audience_data['region'] = response.json().get('data', [])
    print(f"   ✅ {len(audience_data['region'])}개 지역 데이터 수집 완료")

    return audience_data


def fetch_adset_insights(ad_account_id, date_range, access_token):
    """AdSet 레벨 성과 데이터 수집"""
    api_version = 'v19.0'
    base_url = f'https://graph.facebook.com/{api_version}'

    fields = [
        'campaign_id',
        'campaign_name',
        'adset_id',
        'adset_name',
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
        'level': 'adset',
        'limit': 500
    }

    print("📊 AdSet 인사이트 수집 중...")
    url = f'{base_url}/{ad_account_id}/insights'
    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise Exception(f"Meta API 에러 (AdSet): {response.status_code} - {response.text}")

    adset_data = response.json().get('data', [])
    print(f"   ✅ {len(adset_data)}개 AdSet 데이터 수집 완료")
    return adset_data


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


def save_data(data, filename):
    """데이터를 JSON 파일로 저장"""
    output_path = os.path.join(PROJECT_ROOT, 'data', 'raw', filename)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"💾 데이터 저장: {output_path}")
    return output_path


def main():
    """메인 실행 함수"""
    try:
        print("=" * 60)
        print("Meta Ads 데이터 수집 시작")
        print("=" * 60)

        # Access Token 확인
        access_token = get_access_token()

        # 광고 계정 ID
        ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        if not ad_account_id:
            raise ValueError("META_AD_ACCOUNT_ID가 .env에 설정되어야 합니다.")

        print(f"📱 광고 계정: {ad_account_id}")

        # 날짜 범위 설정 (전주 월~일)
        date_range = get_date_range()

        # 데이터 수집
        campaign_data = fetch_campaign_insights(ad_account_id, date_range, access_token)
        audience_data = fetch_audience_insights(ad_account_id, date_range, access_token)
        adset_data = fetch_adset_insights(ad_account_id, date_range, access_token)
        ad_data = fetch_ad_insights(ad_account_id, date_range, access_token)

        # 전체 데이터 구조
        full_data = {
            'collected_at': datetime.now().isoformat(),
            'date_range': date_range,
            'ad_account_id': ad_account_id,
            'campaigns': campaign_data,
            'adsets': adset_data,
            'ads': ad_data,
            'audience': audience_data,
            'summary': {
                'total_campaigns': len(campaign_data),
                'total_adsets': len(adset_data),
                'total_ads': len(ad_data),
                'total_age_segments': len(audience_data.get('age', [])),
                'total_gender_segments': len(audience_data.get('gender', [])),
                'total_region_segments': len(audience_data.get('region', []))
            }
        }

        # 파일명 생성
        filename = f"ads_data_{datetime.now().strftime('%Y-%m-%d')}.json"

        # 저장
        output_path = save_data(full_data, filename)

        print("=" * 60)
        print("✅ 데이터 수집 완료!")
        print(f"   총 캠페인: {full_data['summary']['total_campaigns']}개")
        print(f"   총 Ad: {full_data['summary']['total_ads']}개")
        print(f"   파일 경로: {output_path}")
        print("=" * 60)

        return output_path

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    _ping_healthcheck("start")
    try:
        main()
        _ping_healthcheck("success")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[FATAL] {e}\n{tb}")
        _ping_healthcheck("fail", f"{e}\n{tb}")
        sys.exit(1)
