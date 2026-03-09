"""
MySQL Recruit 관련 테이블 → PostgreSQL recruit 앱 마이그레이션 스크립트
실행: python data_migration/migrate_recruit.py
"""
import os
import sys
import django
from datetime import datetime

# Django 초기화
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

import pymysql
from django.db import connections
from apps.accounts.models import Member
from apps.recruit.models import Company, JobNotice, JobSeeker


def migrate_recruit(dry_run=False):
    """채용 관련 테이블 마이그레이션"""
    print("=" * 60)
    print("채용정보 마이그레이션 시작")
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
        # 1. Company (TBL_JOBOFFER)
        migrate_companies(mysql_conn, dry_run)
        
        # 2. JobNotice (TBL_JOBNOTICE)
        migrate_notices(mysql_conn, dry_run)
        
        # 3. JobSeeker (TBL_JOBHUNTER)
        migrate_seekers(mysql_conn, dry_run)

    finally:
        mysql_conn.close()


def migrate_companies(mysql_conn, dry_run):
    print("
--- 1. 채용회사(TBL_JOBOFFER) 마이그레이션 ---")
    with mysql_conn.cursor() as cursor:
        cursor.execute("SELECT * FROM TBL_JOBOFFER ORDER BY offer_idx")
        rows = cursor.fetchall()

    success, skip, error = 0, 0, 0
    for row in rows:
        try:
            if Company.objects.filter(id=row['offer_idx']).exists():
                skip += 1
                continue

            member = Member.objects.filter(username=row['memb_id']).first()
            if not member:
                # 회원이 없는 경우 스킵하거나 기본 회원 할당 (여기서는 스킵)
                print(f"  스킵 [{row['offer_idx']}]: 회원({row['memb_id']})을 찾을 수 없음")
                skip += 1
                continue

            if not dry_run:
                address = f"{row.get('offer_addr1') or ''} {row.get('offer_addr2') or ''}".strip()
                company = Company(
                    id=row['offer_idx'],
                    member=member,
                    company_name=row['offer_name'] or '이름없음',
                    phone=row.get('offer_tel') or '',
                    email=row.get('offer_email') or '',
                    homepage=row.get('offer_homepage') or '',
                    postal_code=row.get('offer_post') or '',
                    address=address,
                    introduction=row.get('offer_introduce') or '',
                    has_notice=(row.get('offer_noticeflag') == '1'),
                )
                company.save()
            success += 1
        except Exception as e:
            error += 1
            print(f"  오류 [{row['offer_idx']}]: {e}")
    print(f"결과: 성공={success}, 스킵={skip}, 오류={error}")


def migrate_notices(mysql_conn, dry_run):
    print("
--- 2. 채용공고(TBL_JOBNOTICE) 마이그레이션 ---")
    with mysql_conn.cursor() as cursor:
        cursor.execute("SELECT * FROM TBL_JOBNOTICE ORDER BY notice_idx")
        rows = cursor.fetchall()

    success, skip, error = 0, 0, 0
    for row in rows:
        try:
            if JobNotice.objects.filter(id=row['notice_idx']).exists():
                skip += 1
                continue

            member = Member.objects.filter(username=row['memb_id']).first()
            company = Company.objects.filter(id=row['offer_idx']).first()
            
            if not member or not company:
                skip += 1
                continue

            # 직종 (pipe 구분)
            occupations = []
            if row.get('notice_occupation'):
                occupations = [i.strip() for i in str(row['notice_occupation']).split('|') if i.strip()]

            if not dry_run:
                notice = JobNotice(
                    id=row['notice_idx'],
                    member=member,
                    company=company,
                    employment_type=row.get('notice_kind') or '일반',
                    title=row.get('notice_title') or '제목없음',
                    occupations=occupations,
                    career_required=(row.get('notice_career') == '1'),
                    is_approved=(row.get('notice_successflag') == '1'),
                    approval_no=row.get('notice_ack_no') or '',
                    payment_code=row.get('notice_paycode') or '',
                    is_premium=(row.get('notice_premiumflag') == '1'),
                )
                if row.get('notice_premiumstart'):
                    notice.premium_start_date = row['notice_premiumstart']
                if row.get('notice_premiumend'):
                    notice.premium_end_date = row['notice_premiumend']
                
                notice.save()
            success += 1
        except Exception as e:
            error += 1
            print(f"  오류 [{row['notice_idx']}]: {e}")
    print(f"결과: 성공={success}, 스킵={skip}, 오류={error}")


def migrate_seekers(mysql_conn, dry_run):
    print("
--- 3. 구직자(TBL_JOBHUNTER) 마이그레이션 ---")
    with mysql_conn.cursor() as cursor:
        cursor.execute("SELECT * FROM TBL_JOBHUNTER ORDER BY hunter_idx")
        rows = cursor.fetchall()

    success, skip, error = 0, 0, 0
    for row in rows:
        try:
            if JobSeeker.objects.filter(id=row['hunter_idx']).exists():
                skip += 1
                continue

            member = Member.objects.filter(username=row['memb_id']).first()
            if not member:
                skip += 1
                continue

            if not dry_run:
                address = f"{row.get('hunter_addr1') or ''} {row.get('hunter_addr2') or ''}".strip()
                seeker = JobSeeker(
                    id=row['hunter_idx'],
                    member=member,
                    name=row.get('hunter_name') or '이름없음',
                    gender=row.get('hunter_gender') or '',
                    phone=row.get('hunter_hp') or '',
                    email=row.get('hunter_email') or '',
                    address=address,
                    profile_image=row.get('hunter_img') or '',
                    resume_registered=(row.get('hunter_resumeflag') == '1'),
                )
                # 생년월일 처리 (YYYY-MM-DD 형식 가정)
                birth = row.get('hunter_birth')
                if birth and len(str(birth)) >= 8:
                    try:
                        seeker.birth_date = birth
                    except: pass
                
                seeker.save()
            success += 1
        except Exception as e:
            error += 1
            print(f"  오류 [{row['hunter_idx']}]: {e}")
    print(f"결과: 성공={success}, 스킵={skip}, 오류={error}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='실제 저장 없이 시뮬레이션')
    args = parser.parse_args()

    migrate_recruit(dry_run=args.dry_run)
