#!/usr/bin/env python3
"""
주간 리포트 자동화 파이프라인

Meta API 데이터 수집 → 데이터 처리 → Notion 업데이트를 자동으로 실행합니다.
"""

import os
import sys
import time
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
import requests

# 프로젝트 루트 디렉토리
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 환경 변수 로드
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# 로깅 설정
log_dir = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'automation.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def send_slack_notification(message, is_error=False):
    """Slack 웹훅으로 알림 전송"""
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL이 설정되지 않아 Slack 알림을 건너뜁니다.")
        return

    emoji = ":x:" if is_error else ":white_check_mark:"
    color = "#E01E5A" if is_error else "#36A64F"

    payload = {
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{emoji} *Meta Ads Weekly Report*\n{message}"
                        }
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Slack 알림 전송 완료")
        else:
            logger.warning(f"Slack 알림 전송 실패: {response.status_code}")
    except Exception as e:
        logger.warning(f"Slack 알림 전송 중 에러: {e}")


def retry_on_failure(func, max_retries=3, retry_interval=60):
    """재시도 로직"""
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"시도 {attempt}/{max_retries}: {func.__name__}")
            result = func()
            logger.info(f"✅ {func.__name__} 성공")
            return result
        except Exception as e:
            logger.error(f"❌ {func.__name__} 실패 (시도 {attempt}/{max_retries}): {e}")

            if attempt < max_retries:
                logger.info(f"   {retry_interval}초 후 재시도...")
                time.sleep(retry_interval)
            else:
                logger.error(f"   최대 재시도 횟수 초과. 실패.")
                raise


def step1_fetch_meta_data():
    """Step 1: Meta API 데이터 수집"""
    logger.info("=" * 60)
    logger.info("Step 1: Meta API 데이터 수집")
    logger.info("=" * 60)

    # fetch_meta_ads 모듈 import
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts'))
    import fetch_meta_ads

    # 메인 함수 실행
    output_path = fetch_meta_ads.main()
    return output_path


def step2_fetch_notion_leads():
    """Step 2: Notion 문의 데이터 수집"""
    logger.info("=" * 60)
    logger.info("Step 2: Notion 문의 데이터 수집")
    logger.info("=" * 60)

    # fetch_notion_leads 모듈 import
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts'))
    import fetch_notion_leads

    # 날짜 범위 설정 (지난 7일)
    from datetime import date, timedelta
    end_date = date.today()
    start_date = end_date - timedelta(days=7)
    date_range = {
        'since': start_date.strftime('%Y-%m-%d'),
        'until': end_date.strftime('%Y-%m-%d')
    }

    # 메인 함수 실행
    output_path, leads_count = fetch_notion_leads.main(date_range)
    return output_path


def step3_process_data():
    """Step 3: 데이터 처리"""
    logger.info("=" * 60)
    logger.info("Step 3: 데이터 처리")
    logger.info("=" * 60)

    # process_data 모듈 import
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts'))
    import process_data

    # 메인 함수 실행
    output_path = process_data.main()
    return output_path


def step4_send_to_notion():
    """Step 4: Notion 업데이트"""
    logger.info("=" * 60)
    logger.info("Step 4: Notion 업데이트")
    logger.info("=" * 60)

    # send_to_notion 모듈 import
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts'))
    import send_to_notion

    # 메인 함수 실행
    page_url = send_to_notion.main()
    return page_url


def validate_environment():
    """환경 변수 검증"""
    required_vars = [
        'META_ACCESS_TOKEN',
        'META_AD_ACCOUNT_ID',
        'NOTION_TOKEN',
        'NOTION_PARENT_PAGE_ID'
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        raise ValueError(
            f"다음 환경 변수가 .env에 설정되어야 합니다: {', '.join(missing_vars)}"
        )

    logger.info("✅ 환경 변수 검증 완료")


def main():
    """메인 실행 함수"""
    start_time = time.time()

    try:
        logger.info("=" * 60)
        logger.info("Meta Ads Weekly Report 자동화 시작")
        logger.info(f"실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        # 환경 변수 검증
        validate_environment()

        # Step 1: Meta 데이터 수집 (재시도 포함)
        raw_data_path = retry_on_failure(step1_fetch_meta_data)

        # Step 2: Notion 문의 데이터 수집 (재시도 포함)
        notion_leads_path = retry_on_failure(step2_fetch_notion_leads)

        # Step 3: 데이터 처리 (재시도 포함)
        processed_data_path = retry_on_failure(step3_process_data)

        # Step 4: Notion 업데이트 (재시도 포함)
        notion_page_url = retry_on_failure(step4_send_to_notion)

        # 소요 시간 계산
        elapsed_time = time.time() - start_time
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)

        # 성공 메시지
        success_message = (
            f"주간 리포트 생성 완료!\n"
            f"소요 시간: {elapsed_minutes}분 {elapsed_seconds}초\n"
            f"Notion: {notion_page_url}"
        )

        logger.info("=" * 60)
        logger.info("✅ 자동화 완료!")
        logger.info(f"   소요 시간: {elapsed_minutes}분 {elapsed_seconds}초")
        logger.info(f"   Notion URL: {notion_page_url}")
        logger.info("=" * 60)

        # Slack 알림 (성공)
        send_slack_notification(success_message, is_error=False)

        return 0

    except Exception as e:
        # 소요 시간 계산
        elapsed_time = time.time() - start_time
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)

        # 실패 메시지
        error_message = (
            f"주간 리포트 생성 실패\n"
            f"소요 시간: {elapsed_minutes}분 {elapsed_seconds}초\n"
            f"에러: {str(e)}"
        )

        logger.error("=" * 60)
        logger.error("❌ 자동화 실패!")
        logger.error(f"   에러: {e}")
        logger.error("=" * 60)

        # Slack 알림 (실패)
        send_slack_notification(error_message, is_error=True)

        import traceback
        traceback.print_exc()

        return 1


if __name__ == "__main__":
    sys.exit(main())
