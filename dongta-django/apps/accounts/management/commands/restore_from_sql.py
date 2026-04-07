"""
MySQL SQL 덤프 파일에서 TBL_MEMB 데이터를 파싱하여 PostgreSQL로 복원
Usage: python manage.py restore_from_sql <sql_file_path>
"""
import re
import ipaddress
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

            members = self._extract_members_streaming(sql_file, limit)

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

    def _extract_members_streaming(self, sql_file, limit):
        """SQL 파일을 스트리밍 방식으로 읽어 TBL_MEMB INSERT 문 파싱"""
        members = []
        # INSERT INTO `TBL_MEMB` VALUES 라인 패턴
        insert_pattern = re.compile(r'INSERT INTO `TBL_MEMB` VALUES\s*(.+)', re.IGNORECASE)

        with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if len(members) >= limit:
                    break

                line = line.strip()
                match = insert_pattern.match(line)
                if not match:
                    continue

                self.stdout.write("✓ TBL_MEMB INSERT 발견, 행 파싱 중...")
                values_str = match.group(1).rstrip(';')

                # ),(  기준으로 개별 행 분리
                rows = self._split_rows(values_str)
                self.stdout.write(f"  → {len(rows)}개 행 발견")

                for row_str in rows:
                    if len(members) >= limit:
                        break
                    try:
                        member = self._parse_row(row_str.strip().strip('()'))
                        if member:
                            members.append(member)
                    except Exception as e:
                        logger.warning(f"행 파싱 실패: {str(e)}")
                        continue

        return members[:limit]

    def _split_rows(self, values_str):
        """VALUES 문자열을 개별 행으로 분리 (따옴표 안의 ),( 무시)"""
        rows = []
        depth = 0
        in_quotes = False
        start = 0
        i = 0

        while i < len(values_str):
            char = values_str[i]
            if char == "'" and (i == 0 or values_str[i - 1] != '\\'):
                in_quotes = not in_quotes
            elif not in_quotes:
                if char == '(':
                    if depth == 0:
                        start = i
                    depth += 1
                elif char == ')':
                    depth -= 1
                    if depth == 0:
                        rows.append(values_str[start:i + 1])
            i += 1

        return rows

    def _parse_row(self, row_str):
        """SQL VALUES 행을 파싱하여 Member 객체 생성"""
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
            if idx >= len(values):
                return default
            val = values[idx].strip().strip("'")
            return val if val and val.upper() != 'NULL' else default

        memb_id = get_val(1)
        memb_name = get_val(2)
        memb_passwd = get_val(3)
        memb_level = get_val(4, '0')
        memb_email = get_val(5)
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

        if not memb_id or not memb_name or not memb_email:
            return None

        if memb_encrypt_passwd:
            password = memb_encrypt_passwd
        else:
            password = make_password(memb_passwd or 'DefaultPass123!')

        created_at = timezone.now()
        try:
            if memb_regdate and memb_regtime:
                dt = datetime.strptime(f"{memb_regdate} {memb_regtime}", "%Y-%m-%d %H:%M:%S")
                created_at = timezone.make_aware(dt) if not timezone.is_aware(dt) else dt
        except (ValueError, TypeError):
            pass

        try:
            level = int(memb_level) if memb_level else 9
            if level in [1, 2, 3]:
                level = 1
            elif level == 0:
                level = 9
        except ValueError:
            level = 9

        phone = ''
        if memb_hp1 and memb_hp2 and memb_hp3:
            phone = f"{memb_hp1}-{memb_hp2}-{memb_hp3}"

        landline = ''
        if memb_tel1 and memb_tel2 and memb_tel3:
            landline = f"{memb_tel1}-{memb_tel2}-{memb_tel3}"

        postal_code = ''
        if memb_post1 and memb_post2:
            postal_code = f"{memb_post1}{memb_post2}"

        try:
            point = int(memb_point) if memb_point else 0
        except ValueError:
            point = 0

        try:
            login_count = int(memb_logincount) if memb_logincount else 0
        except ValueError:
            login_count = 0

        # IP 유효성 검사
        reg_ip = ''
        if memb_ip:
            try:
                ipaddress.ip_address(memb_ip.strip())
                reg_ip = memb_ip.strip()[:45]
            except ValueError:
                pass

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
            reg_ip=reg_ip,
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
        self.stdout.write(self.style.WARNING(f"\n[DRY RUN] {len(members)}명의 회원을 복원할 예정:"))
        for i, member in enumerate(members[:10], 1):
            self.stdout.write(
                f"  {i}. {member.username} ({member.name}) - {member.email} (Lv.{member.level})"
            )
        if len(members) > 10:
            self.stdout.write(f"  ... 외 {len(members) - 10}명")

    def _save_members(self, members):
        try:
            created = Member.objects.bulk_create(members, ignore_conflicts=True)
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ {len(created)}명의 회원 데이터 복원 완료!')
            )
            total = Member.objects.count()
            active = Member.objects.filter(is_active=True).count()
            self.stdout.write(f"\n📊 현황:")
            self.stdout.write(f"  - 총 회원: {total}명")
            self.stdout.write(f"  - 활성 회원: {active}명")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ 저장 실패: {str(e)}'))
