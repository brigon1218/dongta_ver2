"""
MySQL 포인트/결제 관련 테이블 → PostgreSQL payment 앱 마이그레이션 스크립트
실행: python data_migration/migrate_payment.py
"""
import os
import sys
import django

# Django 초기화
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

import pymysql
from apps.accounts.models import Member
from apps.payment.models import PointAccount, PaymentHistory


def migrate_payment(dry_run=False):
    """포인트 및 결제 내역 마이그레이션"""
    print("=" * 60)
    print("포인트/결제 마이그레이션 시작")
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
        # 1. PointAccount (DongtaPointMain)
        migrate_point_accounts(mysql_conn, dry_run)
        
        # 2. PaymentHistory (DongtaPointCharge)
        migrate_payment_history(mysql_conn, dry_run)

    finally:
        mysql_conn.close()


def migrate_point_accounts(mysql_conn, dry_run):
    print("
--- 1. 포인트 잔액(DongtaPointMain) 마이그레이션 ---")
    with mysql_conn.cursor() as cursor:
        cursor.execute("SELECT * FROM DongtaPointMain")
        rows = cursor.fetchall()

    success, skip, error = 0, 0, 0
    for row in rows:
        try:
            member = Member.objects.filter(username=row['mem_id']).first()
            if not member:
                skip += 1
                continue

            if PointAccount.objects.filter(member=member).exists():
                skip += 1
                continue

            if not dry_run:
                account = PointAccount(
                    member=member,
                    total_charged=int(row.get('nTotalChargeDP') or 0),
                    total_used=int(row.get('nTotalUseDP') or 0),
                )
                account.save()
            success += 1
        except Exception as e:
            error += 1
            print(f"  오류 [{row['mem_id']}]: {e}")
    print(f"결과: 성공={success}, 스킵={skip}, 오류={error}")


def migrate_payment_history(mysql_conn, dry_run):
    print("
--- 2. 결제 내역(DongtaPointCharge) 마이그레이션 ---")
    with mysql_conn.cursor() as cursor:
        cursor.execute("SELECT * FROM DongtaPointCharge ORDER BY nChargeIdx")
        rows = cursor.fetchall()

    success, skip, error = 0, 0, 0
    for row in rows:
        try:
            if PaymentHistory.objects.filter(id=row['nChargeIdx']).exists():
                skip += 1
                continue

            member = Member.objects.filter(username=row['mem_id']).first()
            if not member:
                skip += 1
                continue

            if not dry_run:
                # 결제 수단 매핑
                pay_method = PaymentHistory.PayMethod.CARD
                if row.get('strChargeWay') == 'bank':
                    pay_method = PaymentHistory.PayMethod.BANK_TRANSFER
                elif row.get('strChargeWay') == 'direct':
                    pay_method = PaymentHistory.PayMethod.DIRECT_BANK

                history = PaymentHistory(
                    id=row['nChargeIdx'],
                    member=member,
                    amount=int(row.get('nChargePrice') or 0),
                    point_amount=int(row.get('nChargeDP') or 0),
                    pay_method=pay_method,
                    is_success=(row.get('nChargeSuccessFlag') == 1),
                    result_code=row.get('strChargeAckNo') or '',
                    danal_order_id=row.get('strChargeOrderID'),
                )
                if row.get('dtChargeDate'):
                    history.created_at = row['dtChargeDate']
                if row.get('dtChargeAckDate'):
                    history.confirmed_at = row['dtChargeAckDate']
                
                history.save()
            success += 1
        except Exception as e:
            error += 1
            print(f"  오류 [{row['nChargeIdx']}]: {e}")
    print(f"결과: 성공={success}, 스킵={skip}, 오류={error}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='실제 저장 없이 시뮬레이션')
    args = parser.parse_args()

    migrate_payment(dry_run=args.dry_run)
