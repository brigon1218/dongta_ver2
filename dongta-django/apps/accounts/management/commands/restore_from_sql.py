"""
MySQL SQL 덤프 파일에서 TBL_MEMB 데이터를 파싱하여 PostgreSQL로 복원
Usage: python manage.py restore_from_sql <sql_file_path>
"""
import re
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from apps.accounts.models import Member
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'SQL 덤프 파일에서 TBL_MEMB 데이터를 파싱하여 복원'

    def add_arguments(self, parser):
        parser.add_argument('sql_file', type=str, help='SQL 덤프 파일 경로')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제 저장 없이 미리보기만 실행'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=500,
            help='복원할 최대 회원 수 (기본값: 500)'
        )

    def handle(self, *args, **options):
        sql_file = options['sql_file']
        dry_run = options['dry_run']
        limit = options['limit']

        try:
            self.stdout.write(f"📂 SQL 파일 읽기: {sql_file}")

            with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
                sql_content = f.read()

            self.stdout.write("✓ 파일 로드 완료")

            # TBL_MEMB INSERT 문장 추출
            members = self._extract_members(sql_content, limit)

            if not members:
                self.stdout.write(self.style.WARNING("⚠️  추출된 회원 데이터 없음"))
                return

            self.stdout.write(self.style.SUCCESS(f"✓ {len(members)}명의 회원 데이터 추출됨"))

            if dry_run:
                self._preview_members(members)
            else:
                self._save_members(members)

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"✗ 파일을 찾을 수 없음: {sql_file}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ 오류 발생: {str(e)}"))

    def _extract_members(self, sql_content, limit):
        """SQL 콘텐츠에서 TBL_MEMB INSERT 문 파싱"""
        members = []

        # INSERT INTO `TBL_MEMB` VALUES (...), (...), ... 패턴 찾기
        pattern = r"INSERT INTO `TBL_MEMB` VALUES\s*(.*?)(?=;|INSERT|\Z)"
        matches = re.findall(pattern, sql_content, re.DOTALL | re.IGNORECASE)

        for match in matches:
            # 각 행의 VALUES를 파싱
            rows = re.findall(r'\((.*?)\)(?=,|\s*$)', match, re.DOTALL)

            for row in rows:
                if len(members) >= limit:
                    break

                try:
                    member = self._parse_row(row)
                    if member:
                        members.append(member)
                except Exception as e:
                    logger.warning(f"행 파싱 실패: {str(e)}")
                    continue

            if len(members) >= limit:
                break

        return members[:limit]

    def _parse_row(self, row_str):
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

        # TBL_MEMB 컬럼 순서에 따른 매핑
        # memb_idx, memb_id, memb_name, memb_passwd, memb_level, memb_email, ...
        memb_idx = get_val(0, '0')
        memb_id = get_val(1)
        memb_name = get_val(2)
        memb_passwd = get_val(3)
        memb_level = get_val(4, '0')
        memb_email = get_val(5)
        memb_post1 = get_val(7)
        memb_post2 = get_val(8)
        memb_addr1 = get_val(9)
        memb_addr2 = get_val(10)
        memb_tel1 = get_val(11)
        memb_tel2 = get_val(12)
        memb_tel3 = get_val(13)
        memb_hp1 = get_val(15)
        memb_hp2 = get_val(16)
        memb_hp3 = get_val(17)
        memb_corp = get_val(18)
        memb_region = get_val(19)
        memb_perform = get_val(20)
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

        # 필수 필드 확인
        if not memb_id or not memb_name or not memb_email:
            return None

        # 중복 확인
        if Member.objects.filter(username=memb_id).exists():
            return None

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

    def _preview_members(self, members):
        """복원될 회원 미리보기"""
        self.stdout.write(self.style.WARNING(f"\n[DRY RUN] {len(members)}명의 회원을 복원할 예정:"))
        for i, member in enumerate(members[:10], 1):
            self.stdout.write(
                f"  {i}. {member.username} ({member.name}) - {member.email} (Lv.{member.level})"
            )
        if len(members) > 10:
            self.stdout.write(f"  ... 외 {len(members) - 10}명")

    def _save_members(self, members):
        """회원 데이터 저장"""
        try:
            created = Member.objects.bulk_create(members, ignore_conflicts=True)
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ {len(created)}명의 회원 데이터 복원 완료!')
            )

            # 통계
            total = Member.objects.count()
            active = Member.objects.filter(is_active=True).count()
            self.stdout.write(f"\n📊 현황:")
            self.stdout.write(f"  - 총 회원: {total}명")
            self.stdout.write(f"  - 활성 회원: {active}명")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ 저장 실패: {str(e)}'))
