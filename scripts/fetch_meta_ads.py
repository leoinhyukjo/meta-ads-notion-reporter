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
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 환경 변수 로드
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))


def get_date_range(days=7):
    """지난 N일간의 날짜 범위 반환"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    return {
        'since': start_date.strftime('%Y-%m-%d'),
        'until': end_date.strftime('%Y-%m-%d')
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
        'impressions',
        'clicks',
        'spend',
        'actions',
    ]

    audience_data = {}

    # 연령대별 분석
    print("📊 연령대별 인사이트 수집 중...")
    params = {
        'access_token': access_token,
        'fields': ','.join(fields),
        'time_range': json.dumps(date_range),
        'level': 'account',
        'breakdowns': 'age',
        'limit': 100
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

        # 날짜 범위 설정 (지난 7일)
        date_range = get_date_range(days=7)

        # 데이터 수집
        campaign_data = fetch_campaign_insights(ad_account_id, date_range, access_token)
        audience_data = fetch_audience_insights(ad_account_id, date_range, access_token)

        # 전체 데이터 구조
        full_data = {
            'collected_at': datetime.now().isoformat(),
            'date_range': date_range,
            'ad_account_id': ad_account_id,
            'campaigns': campaign_data,
            'audience': audience_data,
            'summary': {
                'total_campaigns': len(campaign_data),
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
        print(f"   파일 경로: {output_path}")
        print("=" * 60)

        return output_path

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
