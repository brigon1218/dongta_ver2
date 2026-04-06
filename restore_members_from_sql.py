#!/usr/bin/env python3
"""
MySQL SQL 덤프 파일에서 회원 데이터를 추출하여 Django 데이터베이스에 복원하는 스크립트
실제 MySQL 데이터베이스 연결 없이 SQL 파일을 직접 파싱합니다.

Usage:
  python3 restore_members_from_sql.py /path/to/dongta_1022.sql [--dry-run] [--limit 500]
"""
import sys
import re
import os
from datetime import datetime

# Django 설정 초기화
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

import django
django.setup()

from django.utils import timezone
from django.contrib.auth.hashers import make_password
from apps.accounts.models import Member


def extract_members_from_sql(sql_file, limit=500, dry_run=False):
    """SQL 파일에서 TBL_MEMB 데이터를 추출하여 Member 객체 생성"""
    print(f"📂 SQL 파일 읽기: {sql_file}")

    with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
        sql_content = f.read()

    print("✓ 파일 로드 완료")

    # TBL_MEMB INSERT 문장 추출
    members = []
    count = 0

    # INSERT INTO `TBL_MEMB` VALUES (...), (...), ... 패턴 찾기
    pattern = r"INSERT INTO `TBL_MEMB` VALUES\s*(.*?)(?=;|INSERT INTO|\Z)"
    matches = re.findall(pattern, sql_content, re.DOTALL | re.IGNORECASE)

    print(f"📊 {len(matches)}개의 INSERT 블록 발견")

    for block_idx, match in enumerate(matches, 1):
        if count >= limit:
            break

        # 각 행의 VALUES를 파싱
        rows = re.findall(r'\((.*?)\)(?=,|\s*$)', match, re.DOTALL)

        for row_idx, row in enumerate(rows):
            if count >= limit:
                break

            try:
                member = parse_row_to_member(row)
                if member:
                    members.append(member)
                    count += 1

                    if count % 50 == 0:
                        print(f"  ✓ {count}명 추출됨...")

            except Exception as e:
                if row_idx < 5:  # 처음 5개만 에러 출력
                    print(f"  ⚠️  행 {row_idx} 파싱 실패: {str(e)[:50]}")
                continue

        if (block_idx + 1) % 10 == 0:
            print(f"  진행: INSERT 블록 {block_idx}/{len(matches)}")

    print(f"\n✓ 총 {len(members)}명의 회원 데이터 추출됨")

    if not members:
        print("⚠️  추출된 데이터 없음")
        return

    if dry_run:
        preview_members(members)
    else:
        save_members(members)


def parse_row_to_member(row_str):
    """SQL VALUES 행을 파싱하여 Member 객체 생성"""
    # 값 추출 (따옴표 처리)
    values = []
    current = ""
    in_quotes = False

    for i, char in enumerate(row_str):
        if char == "'" and (i == 0 or row_str[i-1] != '\\'):
            in_quotes = not in_quotes
        elif char == ',' and not in_quotes:
            values.append(current.strip())
            current = ""
            continue
        current += char

    if current.strip():
        values.append(current.strip())

    if len(values) < 10:
        return None

    def get_val(idx, default=''):
        """안전한 값 추출"""
        if idx >= len(values):
            return default
        val = values[idx].strip().strip("'")
        return val if val and val.upper() != 'NULL' else default

    # TBL_MEMB 컬럼 순서: memb_idx, memb_id, memb_name, memb_passwd, memb_level, memb_email, ...
    memb_id = get_val(1)
    memb_name = get_val(2)
    memb_email = get_val(5)

    # 필수 필드 확인
    if not memb_id or not memb_name or not memb_email:
        return None

    # 중복 확인
    if Member.objects.filter(username=memb_id).exists():
        return None

    memb_passwd = get_val(3)
    memb_level = get_val(4, '0')
    memb_post1 = get_val(7)
    memb_post2 = get_val(8)
    memb_addr1 = get_val(9)
    memb_tel1 = get_val(11)
    memb_tel2 = get_val(12)
    memb_tel3 = get_val(13)
    memb_hp1 = get_val(15)
    memb_hp2 = get_val(16)
    memb_hp3 = get_val(17)
    memb_corp = get_val(18)
    memb_region = get_val(19)
    memb_class = get_val(21)
    memb_type = get_val(22)
    memb_point = get_val(25, '0')
    memb_regdate = get_val(26)
    memb_regtime = get_val(27)
    memb_ip = get_val(28)
    memb_logincount = get_val(31, '0')
    memb_mailflag = get_val(34, '1')
    memb_wantquitflag = get_val(35, '0')
    memb_abroadflag = get_val(40, '0')
    memb_abroadapplyflag = get_val(41, '0')
    memb_encrypt_passwd = get_val(43, '')

    # 비밀번호 처리
    if memb_encrypt_passwd:
        password = memb_encrypt_passwd
    else:
        password = make_password(memb_passwd or 'DefaultPass123!')

    # 날짜 처리
    created_at = timezone.now()
    try:
        if memb_regdate and memb_regtime:
            dt = datetime.strptime(f"{memb_regdate} {memb_regtime}", "%Y-%m-%d %H:%M:%S")
            created_at = timezone.make_aware(dt) if not timezone.is_aware(dt) else dt
    except (ValueError, TypeError):
        pass

    # 레벨 처리
    try:
        level = int(memb_level) if memb_level else 9
        if level in [1, 2, 3]:
            level = 1
        elif level == 0:
            level = 9
    except ValueError:
        level = 9

    # 전화번호 결합
    phone = ''
    if memb_hp1 and memb_hp2 and memb_hp3:
        phone = f"{memb_hp1}-{memb_hp2}-{memb_hp3}"

    landline = ''
    if memb_tel1 and memb_tel2 and memb_tel3:
        landline = f"{memb_tel1}-{memb_tel2}-{memb_tel3}"

    # 우편번호
    postal_code = ''
    if memb_post1 and memb_post2:
        postal_code = f"{memb_post1}{memb_post2}"

    # 포인트
    try:
        point = int(memb_point) if memb_point else 0
    except ValueError:
        point = 0

    # 로그인 횟수
    try:
        login_count = int(memb_logincount) if memb_logincount else 0
    except ValueError:
        login_count = 0

    return Member(
        username=memb_id.strip()[:50],
        name=memb_name.strip()[:50],
        email=memb_email.strip(),
        password=password,
        level=level,
        postal_code=postal_code[:10],
        address=(memb_addr1 or '')[:200],
        landline=landline[:20],
        phone=phone[:20],
        corp_name=(memb_corp or '')[:100],
        region=(memb_region or '')[:50],
        member_class=(memb_class or '')[:20],
        member_type=(memb_type or '')[:20],
        point=point,
        created_at=created_at,
        reg_ip=(memb_ip or '')[:45],
        login_count=login_count,
        email_opt_in=memb_mailflag != '0',
        want_quit=memb_wantquitflag == '1',
        is_overseas=memb_abroadflag == '1',
        overseas_approved=memb_abroadapplyflag == '1',
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )


def preview_members(members):
    """복원될 회원 미리보기"""
    print(f"\n[DRY RUN] {len(members)}명의 회원을 복원할 예정:")
    for i, member in enumerate(members[:20], 1):
        print(f"  {i}. {member.username:15} | {member.name:10} | {member.email:30} | Lv.{member.level}")
    if len(members) > 20:
        print(f"  ... 외 {len(members) - 20}명")


def save_members(members):
    """회원 데이터 저장"""
    print(f"\n💾 데이터베이스에 저장 중...")
    try:
        created = Member.objects.bulk_create(members, ignore_conflicts=True, batch_size=100)
        print(f"✓ {len(created)}명의 회원 데이터 복원 완료!")

        # 통계
        total = Member.objects.count()
        active = Member.objects.filter(is_active=True).count()
        staff = Member.objects.filter(is_staff=True).count()

        print(f"\n📊 현황:")
        print(f"  - 총 회원: {total}명")
        print(f"  - 활성 회원: {active}명")
        print(f"  - Staff 계정: {staff}명")

    except Exception as e:
        print(f'✗ 저장 실패: {str(e)}')
        raise


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("사용법: python3 restore_members_from_sql.py <sql_file> [--dry-run] [--limit 500]")
        sys.exit(1)

    sql_file = sys.argv[1]
    dry_run = '--dry-run' in sys.argv
    limit = 500

    # --limit 파라미터 확인
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])
            break

    if not os.path.exists(sql_file):
        print(f"❌ 파일을 찾을 수 없음: {sql_file}")
        sys.exit(1)

    extract_members_from_sql(sql_file, limit=limit, dry_run=dry_run)
