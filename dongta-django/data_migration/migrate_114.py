"""
MySQL TBL_YELLOW → PostgreSQL business114_business 마이그레이션 스크립트
실행: python data_migration/migrate_114.py
"""
import os
import sys
import django

# Django 초기화
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

import pymysql
from django.db import connections
from apps.accounts.models import Member
from apps.business114.models import Business, BusinessType


def migrate_114(dry_run=False):
    """TBL_YELLOW → business114_business"""
    print("=" * 60)
    print("동타114 업체 마이그레이션 시작")
    print("=" * 60)

    # MySQL 연결
    mysql_conn = pymysql.connect(
        host=os.environ.get('MYSQL_HOST', 'localhost'),
        user=os.environ.get('MYSQL_USER', ''),
        password=os.environ.get('MYSQL_PASS', ''),
        database='DongtaDB',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )

    try:
        with mysql_conn.cursor() as cursor:
            # TBL_YELLOW의 모든 컬럼 조회
            cursor.execute("SELECT * FROM TBL_YELLOW ORDER BY yellow_idx")
            rows = cursor.fetchall()

        print(f"마이그레이션 대상: {len(rows)}건")

        success_count = 0
        skip_count = 0
        error_count = 0

        for row in rows:
            try:
                # 이미 마이그레이션된 경우 스킵
                if Business.objects.filter(id=row['yellow_idx']).exists():
                    skip_count += 1
                    continue

                # 회원 매칭 (memb_id 기준)
                member = None
                if row['memb_id']:
                    member = Member.objects.filter(username=row['memb_id']).first()

                # 주소 통합
                address = f"{row['yellow_addr1'] or ''} {row['yellow_addr2'] or ''}".strip()

                # 취급 품목 (yellow_item1 ~ yellow_item40+ 가 있을 수 있으나, 보통 문자열로 저장됨)
                # 여기서는 yellow_item 컬럼이 있다면 해당 값을 리스트로 변환
                items = []
                if row.get('yellow_item'):
                    items = [i.strip() for i in str(row['yellow_item']).split('|') if i.strip()]

                if not dry_run:
                    business = Business(
                        id=row['yellow_idx'],
                        member=member,
                        business_type=int(row['yellow_class'] or 1),
                        corp_name=row['yellow_corpname'] or '이름없음',
                        phone=row['yellow_tel'] or '',
                        fax=row['yellow_fax'] or '',
                        homepage=row['yellow_homepage'] or '',
                        postal_code=row['yellow_post'] or '',
                        address=address,
                        industry_type=int(row['yellow_type'] or 0),
                        items=items,
                        location_info=row['yellow_locainfo'] or '',
                        keywords=row['yellow_keyword'] or '',
                        description=row['yellow_desc'] or '',
                        logo_image=row['yellow_img'] or '',
                        view_count=int(row['yellow_hit'] or 0),
                        total_payment=int(row['yellow_totpay'] or 0),
                        approval_no=row['yellow_ack_no'] or '',
                        is_approved=(row['yellow_successflag'] == '1'),
                    )
                    # 생성일 설정 (yellow_regdate 가 문자열 형식일 수 있음)
                    if row.get('yellow_regdate'):
                        business.created_at = row['yellow_regdate']
                    
                    business.save()

                success_count += 1

            except Exception as e:
                error_count += 1
                print(f"  오류 [{row['yellow_idx']}] {row['yellow_corpname']}: {e}")

        print(f"
완료: 성공={success_count}, 스킵={skip_count}, 오류={error_count}")

    finally:
        mysql_conn.close()

    return success_count, error_count


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='실제 저장 없이 시뮬레이션')
    args = parser.parse_args()

    migrate_114(dry_run=args.dry_run)
