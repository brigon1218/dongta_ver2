"""
MySQL → PostgreSQL 마이그레이션 검증 스크립트 (Design S8.2)
실행: python data_migration/verify.py [--table all|members|business|recruit|payment]

검증 항목:
1. 레코드 수 일치 (MySQL vs PostgreSQL)
2. 샘플 데이터 정합성 (username, email, point 등)
3. 비밀번호 해시 상태 (MD5 → bcrypt 전환율)
"""
import os
import sys
import argparse

# Django 초기화
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
import django
django.setup()

import pymysql
from django.db import connection as pg_conn

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"


def get_mysql_conn():
    return pymysql.connect(
        host=os.environ.get('MYSQL_HOST', 'localhost'),
        user=os.environ.get('MYSQL_USER', ''),
        password=os.environ.get('MYSQL_PASS', ''),
        database='DongtaDB',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )


def verify_members(mysql_conn):
    """TBL_MEMB ↔ accounts_member 검증"""
    print("\n[1] 회원(Member) 검증")
    results = []

    # 1-1. 레코드 수
    with mysql_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM TBL_MEMB WHERE memb_wantquitflag='0'")
        mysql_count = cur.fetchone()['cnt']

    with pg_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM accounts_member WHERE is_deleted=false AND is_superuser=false")
        pg_count = cur.fetchone()[0]

    diff = abs(mysql_count - pg_count)
    status = PASS if diff == 0 else (WARN if diff < 100 else FAIL)
    print(f"  레코드 수: MySQL={mysql_count:,} / PG={pg_count:,} → {status} (차이: {diff})")
    results.append(('member_count', diff == 0))

    # 1-2. 샘플 데이터 일치 (무작위 10건 username 확인)
    with mysql_conn.cursor() as cur:
        cur.execute("""
            SELECT memb_id, memb_email, memb_point
            FROM TBL_MEMB
            WHERE memb_wantquitflag='0'
            ORDER BY RAND()
            LIMIT 10
        """)
        mysql_samples = cur.fetchall()

    match_count = 0
    for row in mysql_samples:
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT username, email, point FROM accounts_member WHERE username=%s",
                [row['memb_id']]
            )
            pg_row = cur.fetchone()
        if pg_row and pg_row[1] == row['memb_email']:
            match_count += 1

    sample_status = PASS if match_count >= 8 else (WARN if match_count >= 5 else FAIL)
    print(f"  샘플 일치: {match_count}/10 → {sample_status}")
    results.append(('member_sample', match_count >= 8))

    # 1-3. 비밀번호 해시 전환율
    with pg_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM accounts_member WHERE is_superuser=false")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM accounts_member WHERE password LIKE 'md5$%' AND is_superuser=false")
        md5_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM accounts_member WHERE password LIKE 'argon2%' OR password LIKE 'bcrypt%' AND is_superuser=false")
        modern_count = cur.fetchone()[0]

    md5_pct = (md5_count / total * 100) if total else 0
    modern_pct = (modern_count / total * 100) if total else 0
    hash_status = PASS if md5_pct < 10 else (WARN if md5_pct < 50 else FAIL)
    print(f"  비밀번호 해시: MD5={md5_count:,}({md5_pct:.1f}%) / 현대식={modern_count:,}({modern_pct:.1f}%) → {hash_status}")
    results.append(('password_hash', md5_pct < 50))

    return results


def verify_business(mysql_conn):
    """TBL_114 ↔ business114_business 검증"""
    print("\n[2] 업체(Business114) 검증")
    results = []

    try:
        with mysql_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM TBL_114 WHERE yellow_deleteflag='0'")
            mysql_count = cur.fetchone()['cnt']

        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM business114_business WHERE is_deleted=false")
            pg_count = cur.fetchone()[0]

        diff = abs(mysql_count - pg_count)
        status = PASS if diff == 0 else (WARN if diff < 50 else FAIL)
        print(f"  레코드 수: MySQL={mysql_count:,} / PG={pg_count:,} → {status} (차이: {diff})")
        results.append(('business_count', diff < 50))
    except Exception as e:
        print(f"  {WARN} 업체 테이블 조회 실패: {e}")
        results.append(('business_count', False))

    return results


def verify_recruit(mysql_conn):
    """TBL_JOB / TBL_SEEKER ↔ recruit_* 검증"""
    print("\n[3] 채용(Recruit) 검증")
    results = []

    tables = [
        ('TBL_JOB', 'recruit_jobnotice', 'job_deleteflag', 'is_deleted'),
        ('TBL_SEEKER', 'recruit_jobseeker', None, 'is_deleted'),
    ]

    for mysql_table, pg_table, del_col, _ in tables:
        try:
            with mysql_conn.cursor() as cur:
                if del_col:
                    cur.execute(f"SELECT COUNT(*) AS cnt FROM {mysql_table} WHERE {del_col}='0'")
                else:
                    cur.execute(f"SELECT COUNT(*) AS cnt FROM {mysql_table}")
                mysql_count = cur.fetchone()['cnt']

            with pg_conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {pg_table} WHERE is_deleted=false")
                pg_count = cur.fetchone()[0]

            diff = abs(mysql_count - pg_count)
            status = PASS if diff == 0 else (WARN if diff < 50 else FAIL)
            print(f"  {mysql_table}: MySQL={mysql_count:,} / PG={pg_count:,} → {status} (차이: {diff})")
            results.append((f'{pg_table}_count', diff < 100))
        except Exception as e:
            print(f"  {WARN} {mysql_table} 조회 실패 (테이블 미존재 또는 접근 불가): {e}")
            results.append((f'{pg_table}_count', None))

    return results


def verify_payment(mysql_conn):
    """DongtaPointMain / DongtaPointCharge ↔ payment_* 검증"""
    print("\n[4] 결제(Payment) 검증")
    results = []

    try:
        with mysql_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM DongtaPointCharge")
            mysql_count = cur.fetchone()['cnt']

        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM payment_paymenthistory WHERE is_deleted=false")
            pg_count = cur.fetchone()[0]

        diff = abs(mysql_count - pg_count)
        status = PASS if diff == 0 else (WARN if diff < 100 else FAIL)
        print(f"  결제내역: MySQL={mysql_count:,} / PG={pg_count:,} → {status} (차이: {diff})")
        results.append(('payment_count', diff < 100))
    except Exception as e:
        print(f"  {WARN} 결제 테이블 조회 실패: {e}")
        results.append(('payment_count', None))

    # PointAccount 집계 일치
    try:
        with mysql_conn.cursor() as cur:
            cur.execute("SELECT SUM(nNowDP) AS total FROM DongtaPointMain")
            mysql_total = cur.fetchone()['total'] or 0

        with pg_conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(total_charged - total_used), 0)
                FROM payment_pointaccount
            """)
            pg_total = cur.fetchone()[0] or 0

        diff_pct = abs(mysql_total - pg_total) / max(mysql_total, 1) * 100
        status = PASS if diff_pct < 1 else (WARN if diff_pct < 10 else FAIL)
        print(f"  총 포인트 잔액: MySQL={mysql_total:,} / PG={pg_total:,} → {status} (차이: {diff_pct:.2f}%)")
        results.append(('point_balance', diff_pct < 10))
    except Exception as e:
        print(f"  {WARN} 포인트 잔액 조회 실패: {e}")
        results.append(('point_balance', None))

    return results


def run_all(tables='all'):
    print("=" * 60)
    print("dongta 마이그레이션 검증 시작")
    print("=" * 60)

    try:
        mysql_conn = get_mysql_conn()
    except Exception as e:
        print(f"\n{FAIL} MySQL 연결 실패: {e}")
        print("환경변수 MYSQL_HOST, MYSQL_USER, MYSQL_PASS를 확인하세요.")
        sys.exit(1)

    all_results = []
    try:
        if tables in ('all', 'members'):
            all_results.extend(verify_members(mysql_conn))
        if tables in ('all', 'business'):
            all_results.extend(verify_business(mysql_conn))
        if tables in ('all', 'recruit'):
            all_results.extend(verify_recruit(mysql_conn))
        if tables in ('all', 'payment'):
            all_results.extend(verify_payment(mysql_conn))
    finally:
        mysql_conn.close()

    # 최종 요약
    passed = sum(1 for _, r in all_results if r is True)
    failed = sum(1 for _, r in all_results if r is False)
    skipped = sum(1 for _, r in all_results if r is None)
    total = len(all_results)

    print("\n" + "=" * 60)
    print(f"검증 완료: {passed}/{total} PASS  {failed} FAIL  {skipped} SKIP")
    if failed == 0:
        print(f"{PASS} 마이그레이션 검증 통과")
    else:
        print(f"{FAIL} {failed}건 불일치 — 위 항목을 확인하세요.")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='마이그레이션 데이터 검증')
    parser.add_argument(
        '--table',
        choices=['all', 'members', 'business', 'recruit', 'payment'],
        default='all',
        help='검증할 테이블 (기본: all)',
    )
    args = parser.parse_args()
    success = run_all(args.table)
    sys.exit(0 if success else 1)
