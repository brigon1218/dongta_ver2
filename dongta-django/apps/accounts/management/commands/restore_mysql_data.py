"""
MySQL 백업에서 회원 데이터를 PostgreSQL로 복원하는 관리 명령어
Usage: python manage.py restore_mysql_data
"""
from django.core.management.base import BaseCommand
from django.db import connections
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from apps.accounts.models import Member
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'MySQL 백업에서 회원 데이터를 복원'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='기존 회원 데이터 삭제 후 복원'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제 저장 없이 미리보기만 실행'
        )

    def handle(self, *args, **options):
        clear = options.get('clear', False)
        dry_run = options.get('dry_run', False)

        try:
            # MySQL 레거시 DB 연결 확인
            legacy_db = connections['legacy']
            with legacy_db.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM TBL_MEMB")
                count = cursor.fetchone()[0]
                self.stdout.write(
                    self.style.SUCCESS(f'✓ MySQL 연결 성공. 회원 수: {count}')
                )

                # 기존 데이터 삭제
                if clear and not dry_run:
                    Member.objects.filter(username__startswith='user').delete()
                    self.stdout.write(
                        self.style.WARNING('⚠ 테스트 회원 데이터(user*) 삭제됨')
                    )

                # 데이터 복원
                self._restore_members(cursor, dry_run)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ 오류 발생: {str(e)}')
            )

    def _restore_members(self, cursor, dry_run=False):
        """TBL_MEMB에서 회원 데이터 복원"""
        cursor.execute("""
            SELECT
                memb_idx, memb_id, memb_name, memb_email,
                memb_encrypt_passwd, memb_passwd,
                memb_level, memb_post1, memb_post2, memb_addr1,
                memb_tel1, memb_tel2, memb_tel3, memb_tel4,
                memb_hp1, memb_hp2, memb_hp3,
                memb_corp, memb_region, memb_class, memb_type,
                memb_point, memb_regdate, memb_regtime, memb_ip,
                memb_logincount, memb_mailflag, memb_wantquitflag,
                memb_abroadflag, memb_abroadapplyflag
            FROM TBL_MEMB
            WHERE memb_id IS NOT NULL AND memb_id != ''
            LIMIT 500
        """)

        members_to_create = []
        errors = []

        for row in cursor.fetchall():
            try:
                member_data = self._map_row_to_member(row)
                if member_data:
                    members_to_create.append(member_data)
            except Exception as e:
                errors.append(f"Row {row[0]}: {str(e)}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'\n[DRY RUN] {len(members_to_create)}명의 회원을 복원할 예정:')
            )
            for i, member in enumerate(members_to_create[:5], 1):
                self.stdout.write(
                    f"  {i}. {member.username} ({member.name}) - {member.email}"
                )
            if len(members_to_create) > 5:
                self.stdout.write(f"  ... 외 {len(members_to_create) - 5}명")
        else:
            # 데이터 저장
            if members_to_create:
                Member.objects.bulk_create(members_to_create, ignore_conflicts=True)
                self.stdout.write(
                    self.style.SUCCESS(f'✓ {len(members_to_create)}명의 회원 데이터 복원 완료')
                )

        if errors:
            self.stdout.write(
                self.style.WARNING(f'\n⚠ {len(errors)}개의 오류 발생:')
            )
            for error in errors[:10]:
                self.stdout.write(f"  - {error}")

    def _map_row_to_member(self, row):
        """MySQL 행을 Django Member 객체로 변환"""
        (memb_idx, memb_id, memb_name, memb_email,
         memb_encrypt_passwd, memb_passwd,
         memb_level, memb_post1, memb_post2, memb_addr1,
         memb_tel1, memb_tel2, memb_tel3, memb_tel4,
         memb_hp1, memb_hp2, memb_hp3,
         memb_corp, memb_region, memb_class, memb_type,
         memb_point, memb_regdate, memb_regtime, memb_ip,
         memb_logincount, memb_mailflag, memb_wantquitflag,
         memb_abroadflag, memb_abroadapplyflag) = row

        # 필수 필드 검증
        if not memb_id or not memb_name or not memb_email:
            return None

        # 기존 회원 확인 (중복 방지)
        if Member.objects.filter(username=memb_id).exists():
            return None

        # 비밀번호 처리
        # memb_encrypt_passwd가 있으면 사용, 없으면 raw password 해싱
        if memb_encrypt_passwd:
            password = memb_encrypt_passwd
        else:
            # MD5 해시는 Django에서 인식 불가, 새로 생성
            password = make_password(memb_passwd or 'DefaultPass123!')

        # 우편번호 결합
        postal_code = ''
        if memb_post1 and memb_post2:
            postal_code = f"{memb_post1}{memb_post2}"

        # 전화번호 결합
        landline = ''
        if memb_tel1 and memb_tel2 and memb_tel3:
            landline = f"{memb_tel1}-{memb_tel2}-{memb_tel3}"
        elif memb_tel4:
            landline = memb_tel4

        phone = ''
        if memb_hp1 and memb_hp2 and memb_hp3:
            phone = f"{memb_hp1}-{memb_hp2}-{memb_hp3}"

        # 가입 시간 병합
        created_at = timezone.now()
        try:
            if memb_regdate and memb_regtime:
                dt = datetime.combine(memb_regdate, memb_regtime)
                created_at = timezone.make_aware(dt) if not timezone.is_aware(dt) else dt
        except (TypeError, ValueError):
            pass

        # 레벨 변환 (MySQL: 0=user, 1=staff → Django: 9=user, 1=admin)
        level = 9
        if memb_level and int(memb_level) in [1, 2, 3]:  # 스태프/관리자
            level = 1
        elif memb_level:
            level = int(memb_level)

        return Member(
            username=memb_id.strip(),
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
            point=int(memb_point) if memb_point else 0,
            created_at=created_at,
            reg_ip=(memb_ip or '')[:45],
            login_count=int(memb_logincount) if memb_logincount else 0,
            email_opt_in=memb_mailflag != '0',
            want_quit=memb_wantquitflag == '1',
            is_overseas=memb_abroadflag == '1',
            overseas_approved=memb_abroadapplyflag == '1',
            is_active=True,
            is_staff=level == 1,
            is_superuser=False,
        )
