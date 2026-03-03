#!/usr/bin/env python3
"""
Meta Ads 데이터 처리 스크립트

원본 데이터를 분석하여 주요 메트릭을 계산하고 Notion 형식으로 변환합니다.
- 메트릭 계산: CPC, CTR, CPA, ROAS
- 캠페인별 성과 분석
- 오디언스 인사이트 정리
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 디렉토리
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def get_latest_raw_data():
    """data/raw/에서 가장 최근 데이터 파일 찾기"""
    raw_dir = os.path.join(PROJECT_ROOT, 'data', 'raw')
    json_files = list(Path(raw_dir).glob('ads_data_*.json'))

    if not json_files:
        raise FileNotFoundError(f"data/raw/ 디렉토리에 데이터 파일이 없습니다.")

    latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
    print(f"📂 Meta 광고 데이터 로드: {latest_file}")

    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data


def get_latest_notion_leads():
    """data/raw/에서 가장 최근 Notion 문의 데이터 찾기"""
    raw_dir = os.path.join(PROJECT_ROOT, 'data', 'raw')
    json_files = list(Path(raw_dir).glob('notion_leads_*.json'))

    if not json_files:
        print("⚠️  Notion 문의 데이터를 찾을 수 없습니다. 전환 수를 0으로 계산합니다.")
        return {'total_leads': 0, 'leads': []}

    latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
    print(f"📂 Notion 문의 데이터 로드: {latest_file}")

    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data


def safe_float(value, default=0.0):
    """안전하게 float 변환"""
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    """안전하게 int 변환"""
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        return default


def extract_actions(actions, action_type):
    """actions 배열에서 특정 action_type의 값 추출"""
    if not actions or not isinstance(actions, list):
        return 0

    for action in actions:
        if action.get('action_type') == action_type:
            return safe_int(action.get('value', 0))

    return 0


def extract_action_values(action_values, action_type):
    """action_values 배열에서 특정 action_type의 값 추출"""
    if not action_values or not isinstance(action_values, list):
        return 0.0

    for action in action_values:
        if action.get('action_type') == action_type:
            return safe_float(action.get('value', 0))

    return 0.0


def calculate_metrics(campaign):
    """캠페인 메트릭 계산"""
    impressions = safe_int(campaign.get('impressions', 0))
    clicks = safe_int(campaign.get('clicks', 0))
    spend = safe_float(campaign.get('spend', 0))

    # 전환 데이터 추출
    actions = campaign.get('actions', [])
    action_values = campaign.get('action_values', [])

    # 주요 전환 타입
    purchase = extract_actions(actions, 'purchase')
    lead = extract_actions(actions, 'lead')
    add_to_cart = extract_actions(actions, 'add_to_cart')
    link_click = extract_actions(actions, 'link_click')

    # 전환 가치
    purchase_value = extract_action_values(action_values, 'purchase')
    total_conversion_value = extract_action_values(action_values, 'omni_purchase')

    # 총 전환 수 (purchase + lead)
    total_conversions = purchase + lead

    # 메트릭 계산
    cpc = spend / clicks if clicks > 0 else 0
    ctr = (clicks / impressions * 100) if impressions > 0 else 0
    cpa = spend / total_conversions if total_conversions > 0 else 0
    roas = total_conversion_value / spend if spend > 0 else 0

    return {
        'campaign_id': campaign.get('campaign_id'),
        'campaign_name': campaign.get('campaign_name'),
        'impressions': impressions,
        'clicks': clicks,
        'spend': round(spend, 2),
        'reach': safe_int(campaign.get('reach', 0)),
        'frequency': safe_float(campaign.get('frequency', 0)),
        'cpc': round(cpc, 2),
        'ctr': round(ctr, 2),
        'cpm': safe_float(campaign.get('cpm', 0)),
        'conversions': {
            'purchase': purchase,
            'lead': lead,
            'add_to_cart': add_to_cart,
            'link_click': link_click,
            'total': total_conversions
        },
        'conversion_value': {
            'purchase': round(purchase_value, 2),
            'total': round(total_conversion_value, 2)
        },
        'cpa': round(cpa, 2),
        'roas': round(roas, 2)
    }


def process_campaigns(campaigns):
    """모든 캠페인 데이터 처리"""
    print(f"📊 {len(campaigns)}개 캠페인 처리 중...")

    processed_campaigns = []
    for campaign in campaigns:
        metrics = calculate_metrics(campaign)
        processed_campaigns.append(metrics)

    # 지출 순으로 정렬
    processed_campaigns.sort(key=lambda x: x['spend'], reverse=True)

    print(f"   ✅ 캠페인 처리 완료")
    return processed_campaigns


def process_audience_data(audience_data):
    """오디언스 데이터를 캠페인별로 그룹화하여 처리"""
    print("📊 오디언스 데이터 처리 중...")

    # 캠페인별 그룹화
    by_campaign: dict[str, dict] = {}

    for breakdown_type in ('age', 'gender', 'region'):
        for segment in audience_data.get(breakdown_type, []):
            cid = segment.get('campaign_id', 'unknown')
            if cid not in by_campaign:
                by_campaign[cid] = {
                    'campaign_name': segment.get('campaign_name', ''),
                    'age': [], 'gender': [], 'region': []
                }

            entry = {
                'impressions': safe_int(segment.get('impressions', 0)),
                'clicks': safe_int(segment.get('clicks', 0)),
                'spend': round(safe_float(segment.get('spend', 0)), 2),
            }

            if breakdown_type == 'age':
                entry['age'] = segment.get('age', 'Unknown')
            elif breakdown_type == 'gender':
                entry['gender'] = segment.get('gender', 'Unknown')
            elif breakdown_type == 'region':
                entry['region'] = segment.get('region', 'Unknown')

            by_campaign[cid][breakdown_type].append(entry)

    # 각 캠페인 내 지출 순 정렬
    for cid, data in by_campaign.items():
        data['age'].sort(key=lambda x: x['spend'], reverse=True)
        data['gender'].sort(key=lambda x: x['spend'], reverse=True)
        data['region'].sort(key=lambda x: x['spend'], reverse=True)

    print(f"   ✅ 오디언스 데이터 처리 완료 ({len(by_campaign)}개 캠페인)")
    return by_campaign


def process_adset_data(raw_adsets):
    """AdSet 데이터를 캠페인별로 그룹화하여 처리"""
    print("📊 AdSet 데이터 처리 중...")

    by_campaign: dict[str, list] = {}

    for adset in raw_adsets:
        cid = adset.get('campaign_id', 'unknown')
        if cid not in by_campaign:
            by_campaign[cid] = []

        impressions = safe_int(adset.get('impressions', 0))
        clicks = safe_int(adset.get('clicks', 0))
        spend = round(safe_float(adset.get('spend', 0)), 2)

        # 전환 추출
        actions = adset.get('actions', [])
        lead = extract_actions(actions, 'lead')
        purchase = extract_actions(actions, 'purchase')
        total_conversions = lead + purchase

        by_campaign[cid].append({
            'adset_id': adset.get('adset_id'),
            'adset_name': adset.get('adset_name', ''),
            'impressions': impressions,
            'clicks': clicks,
            'spend': spend,
            'reach': safe_int(adset.get('reach', 0)),
            'frequency': round(safe_float(adset.get('frequency', 0)), 2),
            'cpc': round(spend / clicks, 2) if clicks > 0 else 0,
            'ctr': round(clicks / impressions * 100, 2) if impressions > 0 else 0,
            'cpm': round(safe_float(adset.get('cpm', 0)), 2),
            'conversions': total_conversions,
            'cpa': round(spend / total_conversions, 2) if total_conversions > 0 else 0,
        })

    # 각 캠페인 내 지출 순 정렬
    for cid in by_campaign:
        by_campaign[cid].sort(key=lambda x: x['spend'], reverse=True)

    total = sum(len(v) for v in by_campaign.values())
    print(f"   ✅ AdSet 데이터 처리 완료 ({total}개 AdSet, {len(by_campaign)}개 캠페인)")
    return by_campaign


def process_ad_data(raw_ads):
    """Ad(소재) 데이터를 캠페인별로 그룹화하여 처리"""
    print("📊 Ad 데이터 처리 중...")

    by_campaign: dict[str, list] = {}

    for ad in raw_ads:
        cid = ad.get('campaign_id', 'unknown')
        if cid not in by_campaign:
            by_campaign[cid] = []

        impressions = safe_int(ad.get('impressions', 0))
        clicks = safe_int(ad.get('clicks', 0))
        spend = round(safe_float(ad.get('spend', 0)), 2)

        # 전환 추출
        actions = ad.get('actions', [])
        lead = extract_actions(actions, 'lead')
        purchase = extract_actions(actions, 'purchase')
        total_conversions = lead + purchase

        by_campaign[cid].append({
            'ad_id': ad.get('ad_id'),
            'ad_name': ad.get('ad_name', ''),
            'adset_name': ad.get('adset_name', ''),
            'impressions': impressions,
            'clicks': clicks,
            'spend': spend,
            'reach': safe_int(ad.get('reach', 0)),
            'frequency': round(safe_float(ad.get('frequency', 0)), 2),
            'cpc': round(spend / clicks, 2) if clicks > 0 else 0,
            'ctr': round(clicks / impressions * 100, 2) if impressions > 0 else 0,
            'conversions': total_conversions,
        })

    # 각 캠페인 내 지출 순 정렬
    for cid in by_campaign:
        by_campaign[cid].sort(key=lambda x: x['spend'], reverse=True)

    total = sum(len(v) for v in by_campaign.values())
    print(f"   ✅ Ad 데이터 처리 완료 ({total}개 Ad, {len(by_campaign)}개 캠페인)")
    return by_campaign


def calculate_summary(processed_campaigns, notion_leads_count=0):
    """주간 요약 통계 계산"""
    print("📊 주간 요약 계산 중...")

    total_spend = sum(c['spend'] for c in processed_campaigns)
    total_impressions = sum(c['impressions'] for c in processed_campaigns)
    total_clicks = sum(c['clicks'] for c in processed_campaigns)

    # 🔥 실제 전환 = Notion 문의 수
    total_conversions = notion_leads_count

    # 전환 가치 (문의 1건당 평균 가치 USD, 필요시 수정)
    avg_lead_value = 500  # $500 (조정 가능)
    total_conversion_value = total_conversions * avg_lead_value

    avg_cpc = total_spend / total_clicks if total_clicks > 0 else 0
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    avg_cpa = total_spend / total_conversions if total_conversions > 0 else 0
    roas = total_conversion_value / total_spend if total_spend > 0 else 0

    summary = {
        'total_spend': round(total_spend, 2),
        'total_impressions': total_impressions,
        'total_clicks': total_clicks,
        'total_conversions': total_conversions,
        'total_conversion_value': round(total_conversion_value, 2),
        'avg_cpc': round(avg_cpc, 2),
        'avg_ctr': round(avg_ctr, 2),
        'avg_cpa': round(avg_cpa, 2),
        'roas': round(roas, 2),
        'campaign_count': len(processed_campaigns)
    }

    print(f"   ✅ 요약 계산 완료")
    print(f"      총 지출: ${summary['total_spend']:,.2f}")
    print(f"      총 노출: {summary['total_impressions']:,}회")
    print(f"      총 전환 (문의): {summary['total_conversions']}개")
    print(f"      평균 CPA: ${summary['avg_cpa']:,.2f}")

    return summary


def save_processed_data(data, filename):
    """처리된 데이터를 JSON 파일로 저장"""
    output_path = os.path.join(PROJECT_ROOT, 'data', 'processed', filename)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"💾 처리된 데이터 저장: {output_path}")
    return output_path


def main():
    """메인 실행 함수"""
    try:
        print("=" * 60)
        print("Meta Ads 데이터 처리 시작")
        print("=" * 60)

        # 원본 데이터 로드
        raw_data = get_latest_raw_data()

        # Notion 문의 데이터 로드
        notion_leads_data = get_latest_notion_leads()
        notion_leads_count = notion_leads_data.get('total_leads', 0)

        # 캠페인 데이터 처리
        processed_campaigns = process_campaigns(raw_data.get('campaigns', []))

        # 오디언스 데이터를 캠페인별로 그룹화
        audience_by_campaign = process_audience_data(raw_data.get('audience', {}))

        # AdSet 데이터를 캠페인별로 그룹화
        adset_by_campaign = process_adset_data(raw_data.get('adsets', []))

        # Ad 데이터를 캠페인별로 그룹화
        ad_by_campaign = process_ad_data(raw_data.get('ads', []))

        # 캠페인에 오디언스 + AdSet + Ad 데이터 매핑
        for campaign in processed_campaigns:
            cid = campaign['campaign_id']
            campaign['audience'] = audience_by_campaign.get(cid, {
                'age': [], 'gender': [], 'region': []
            })
            campaign['adsets'] = adset_by_campaign.get(cid, [])
            campaign['ads'] = ad_by_campaign.get(cid, [])

        # 주간 요약 계산 (Notion 문의 수를 실제 전환으로 사용)
        summary = calculate_summary(processed_campaigns, notion_leads_count)

        # 전체 처리 결과
        processed_data = {
            'processed_at': datetime.now().isoformat(),
            'date_range': raw_data.get('date_range', {}),
            'summary': summary,
            'campaigns': processed_campaigns,
            'metadata': {
                'source_file': raw_data.get('collected_at'),
                'ad_account_id': raw_data.get('ad_account_id')
            }
        }

        # 파일명 생성
        filename = f"weekly_report_{datetime.now().strftime('%Y-%m-%d')}.json"

        # 저장
        output_path = save_processed_data(processed_data, filename)

        print("=" * 60)
        print("✅ 데이터 처리 완료!")
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
