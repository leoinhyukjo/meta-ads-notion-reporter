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
from datetime import datetime, timedelta
from dotenv import load_dotenv
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adsinsights import AdsInsights

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


def initialize_api():
    """Meta API 초기화"""
    app_id = os.getenv('META_APP_ID')
    app_secret = os.getenv('META_APP_SECRET')
    access_token = os.getenv('META_ACCESS_TOKEN')

    if not all([app_id, app_secret, access_token]):
        raise ValueError("META_APP_ID, META_APP_SECRET, META_ACCESS_TOKEN이 .env에 설정되어야 합니다.")

    FacebookAdsApi.init(app_id, app_secret, access_token)
    print("✅ Meta API 인증 완료")


def fetch_campaign_insights(ad_account_id, date_range):
    """캠페인별 성과 데이터 수집"""
    account = AdAccount(ad_account_id)

    # 수집할 필드
    fields = [
        AdsInsights.Field.campaign_id,
        AdsInsights.Field.campaign_name,
        AdsInsights.Field.impressions,
        AdsInsights.Field.clicks,
        AdsInsights.Field.spend,
        AdsInsights.Field.reach,
        AdsInsights.Field.frequency,
        AdsInsights.Field.cpc,
        AdsInsights.Field.cpm,
        AdsInsights.Field.cpp,
        AdsInsights.Field.ctr,
        AdsInsights.Field.actions,
        AdsInsights.Field.action_values,
        AdsInsights.Field.cost_per_action_type,
    ]

    # 파라미터
    params = {
        'time_range': date_range,
        'level': 'campaign',
        'filtering': [],
        'limit': 500
    }

    print(f"📊 캠페인 인사이트 수집 중... ({date_range['since']} ~ {date_range['until']})")

    insights = account.get_insights(fields=fields, params=params)

    # 결과를 딕셔너리 리스트로 변환
    campaign_data = []
    for insight in insights:
        campaign_data.append(dict(insight))

    print(f"   ✅ {len(campaign_data)}개 캠페인 데이터 수집 완료")
    return campaign_data


def fetch_audience_insights(ad_account_id, date_range):
    """오디언스 breakdown 데이터 수집"""
    account = AdAccount(ad_account_id)

    fields = [
        AdsInsights.Field.impressions,
        AdsInsights.Field.clicks,
        AdsInsights.Field.spend,
        AdsInsights.Field.actions,
    ]

    audience_data = {}

    # 연령대별 분석
    print("📊 연령대별 인사이트 수집 중...")
    age_insights = account.get_insights(
        fields=fields,
        params={
            'time_range': date_range,
            'level': 'account',
            'breakdowns': ['age'],
            'limit': 100
        }
    )
    audience_data['age'] = [dict(insight) for insight in age_insights]
    print(f"   ✅ {len(audience_data['age'])}개 연령대 데이터 수집 완료")

    # 성별 분석
    print("📊 성별 인사이트 수집 중...")
    gender_insights = account.get_insights(
        fields=fields,
        params={
            'time_range': date_range,
            'level': 'account',
            'breakdowns': ['gender'],
            'limit': 100
        }
    )
    audience_data['gender'] = [dict(insight) for insight in gender_insights]
    print(f"   ✅ {len(audience_data['gender'])}개 성별 데이터 수집 완료")

    # 지역별 분석
    print("📊 지역별 인사이트 수집 중...")
    region_insights = account.get_insights(
        fields=fields,
        params={
            'time_range': date_range,
            'level': 'account',
            'breakdowns': ['region'],
            'limit': 100
        }
    )
    audience_data['region'] = [dict(insight) for insight in region_insights]
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

        # API 초기화
        initialize_api()

        # 광고 계정 ID
        ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        if not ad_account_id:
            raise ValueError("META_AD_ACCOUNT_ID가 .env에 설정되어야 합니다.")

        print(f"📱 광고 계정: {ad_account_id}")

        # 날짜 범위 설정 (지난 7일)
        date_range = get_date_range(days=7)

        # 데이터 수집
        campaign_data = fetch_campaign_insights(ad_account_id, date_range)
        audience_data = fetch_audience_insights(ad_account_id, date_range)

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
