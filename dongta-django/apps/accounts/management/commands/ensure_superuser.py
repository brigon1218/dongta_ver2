"""
관리자 슈퍼유저 계정 보장 커맨드.
컨테이너 시작 시 자동 실행하여 환경변수에 정의된 슈퍼유저를 항상 유지.
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from django.db import connection


class Command(BaseCommand):
    help = '슈퍼유저 계정을 환경변수 기준으로 생성/갱신'

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Admin1234!')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@dongta.theuit.info')
        hashed = make_password(password)

        # 시그널·auto_now 우회: 직접 SQL로 upsert
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO accounts_member
                    (username, password, email, name, is_staff, is_superuser, is_active,
                     level, created_at, updated_at, is_deleted,
                     phone, landline, postal_code, address, region,
                     corp_name, member_type, member_class, point,
                     email_opt_in, is_overseas, overseas_approved,
                     login_count, want_quit)
                VALUES
                    (%s, %s, %s, %s, TRUE, TRUE, TRUE,
                     1, NOW(), NOW(), FALSE,
                     '', '', '', '', '',
                     '', '', '', 0,
                     TRUE, FALSE, FALSE,
                     0, FALSE)
                ON CONFLICT (username) DO UPDATE SET
                    password    = EXCLUDED.password,
                    email       = EXCLUDED.email,
                    is_staff    = TRUE,
                    is_superuser= TRUE,
                    is_active   = TRUE,
                    updated_at  = NOW()
                """,
                [username, hashed, email, '관리자']
            )

        self.stdout.write(self.style.SUCCESS(
            f'슈퍼유저 보장 완료: {username}'
        ))
