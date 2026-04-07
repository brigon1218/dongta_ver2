"""
관리자 슈퍼유저 계정 보장 커맨드.
컨테이너 시작 시 자동 실행하여 환경변수에 정의된 슈퍼유저를 항상 유지.
"""
import os
from django.core.management.base import BaseCommand
from apps.accounts.models import Member


class Command(BaseCommand):
    help = '슈퍼유저 계정을 환경변수 기준으로 생성/갱신'

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Admin1234!')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@dongta.theuit.info')

        user, created = Member.objects.update_or_create(
            username=username,
            defaults={
                'email': email,
                'name': '관리자',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        user.set_password(password)
        user.save(update_fields=['password'])

        action = '생성' if created else '갱신'
        self.stdout.write(self.style.SUCCESS(
            f'슈퍼유저 {action} 완료: {username}'
        ))
