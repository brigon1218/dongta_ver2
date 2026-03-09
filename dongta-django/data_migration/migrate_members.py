"""
MySQL TBL_MEMB → PostgreSQL accounts_member 마이그레이션 스크립트
실행: python data_migration/migrate_members.py
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


def normalize_phone(p1, p2, p3):
    """전화번호 3컬럼 → 표준 형식 (010-1234-5678)"""
    parts = [str(p).strip() for p in [p1, p2, p3] if p and str(p).strip()]
    if len(parts) == 3:
        return '-'.join(parts)
    return ''.join(parts)


def migrate_members(dry_run=False):
    """TBL_MEMB → accounts_member"""
    print("=" * 60)
    print("회원 마이그레이션 시작")
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
            cursor.execute("""
                SELECT
                    memb_idx, memb_id, memb_encrypt_passwd,
                    memb_name, memb_email, memb_level,
                    memb_hp1, memb_hp2, memb_hp3,
                    memb_tel1, memb_tel2, memb_tel3,
                    memb_post1, memb_post2,
                    memb_addr1, memb_addr2,
                    memb_region, memb_corp,
                    memb_type, memb_class,
                    memb_point, memb_mailflag,
                    memb_abroadflag, memb_abroadapplyflag,
                    memb_logincount, memb_text, memb_ip,
                    memb_wantquitflag, memb_quitreason,
                    memb_regdate
                FROM TBL_MEMB
                WHERE memb_wantquitflag = '0'
                ORDER BY memb_idx
            """)
            rows = cursor.fetchall()

        print(f"마이그레이션 대상: {len(rows)}명")

        success_count = 0
        skip_count = 0
        error_count = 0

        for row in rows:
            try:
                # 이미 마이그레이션된 경우 스킵
                if Member.objects.filter(id=row['memb_idx']).exists():
                    skip_count += 1
                    continue

                phone = normalize_phone(row['memb_hp1'], row['memb_hp2'], row['memb_hp3'])
                landline = normalize_phone(row['memb_tel1'], row['memb_tel2'], row['memb_tel3'])
                address = f"{row['memb_addr1'] or ''} {row['memb_addr2'] or ''}".strip()
                postal_code = f"{row['memb_post1'] or ''}{row['memb_post2'] or ''}".strip()

                if not dry_run:
                    member = Member(
                        id=row['memb_idx'],
                        username=row['memb_id'],
                        name=row['memb_name'] or '',
                        email=row['memb_email'] or f"unknown_{row['memb_idx']}@dongta.com",
                        level=int(row['memb_level'] or 9),
                        phone=phone,
                        landline=landline,
                        postal_code=postal_code,
                        address=address,
                        region=row['memb_region'] or '',
                        corp_name=row['memb_corp'] or '',
                        member_type=row['memb_type'] or '',
                        member_class=row['memb_class'] or '',
                        point=int(row['memb_point'] or 0),
                        email_opt_in=(row['memb_mailflag'] == '1'),
                        is_overseas=(row['memb_abroadflag'] == '1'),
                        overseas_approved=(row['memb_abroadapplyflag'] == '1'),
                        login_count=int(row['memb_logincount'] or 0),
                        memo=row['memb_text'] or '',
                        reg_ip=row['memb_ip'] or None,
                        want_quit=False,
                        is_active=True,
                    )
                    # 패스워드: md5 임시 저장 (첫 로그인 시 Argon2로 업그레이드)
                    member.password = f"md5${row['memb_encrypt_passwd']}"
                    member.save()

                success_count += 1

            except Exception as e:
                error_count += 1
                print(f"  오류 [{row['memb_idx']}] {row['memb_id']}: {e}")

        print(f"\n완료: 성공={success_count}, 스킵={skip_count}, 오류={error_count}")

    finally:
        mysql_conn.close()

    return success_count, error_count


def verify_migration():
    """마이그레이션 결과 검증"""
    pg_count = Member.objects.filter(is_active=True).count()
    print(f"\n검증: PostgreSQL 회원 수 = {pg_count}")
    return pg_count


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='실제 저장 없이 시뮬레이션')
    args = parser.parse_args()

    migrate_members(dry_run=args.dry_run)
    if not args.dry_run:
        verify_migration()
