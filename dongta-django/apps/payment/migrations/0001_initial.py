# Generated migration for PaymentHistory model with Danal integration

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PointAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_charged', models.IntegerField(default=0, help_text='누적 충전액 (원)')),
                ('total_used', models.IntegerField(default=0, help_text='누적 사용액 (원)')),
                ('last_charged_at', models.DateTimeField(blank=True, null=True, verbose_name='마지막 충전 시간')),
                ('last_used_at', models.DateTimeField(blank=True, null=True, verbose_name='마지막 사용 시간')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성 시간')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정 시간')),
                ('member', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '포인트 계정',
                'verbose_name_plural': '포인트 계정',
                'db_table': 'payment_pointaccount',
                'ordering': ['-updated_at'],
                'indexes': [
                    models.Index(fields=['member'], name='member_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='PaymentHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.IntegerField(help_text='결제 금액 (원)')),
                ('point_amount', models.IntegerField(help_text='포인트 적립량 (원)')),
                ('pay_method', models.CharField(choices=[('CARD', '신용카드'), ('ACCOUNT', '계좌이체'), ('PHONE', '휴대폰')], max_length=20, verbose_name='결제 수단')),
                ('is_success', models.BooleanField(default=False, verbose_name='결제 성공 여부')),
                ('result_code', models.CharField(blank=True, max_length=50, verbose_name='결과 코드')),
                ('result_message', models.TextField(blank=True, verbose_name='결과 메시지')),
                ('danal_order_id', models.CharField(blank=True, max_length=100, verbose_name='다날 주문 ID')),
                ('confirmed_at', models.DateTimeField(blank=True, null=True, verbose_name='승인 시간')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성 시간')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정 시간')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='삭제 여부')),
                # Danal integration fields (Phase 2-3)
                ('tid', models.CharField(blank=True, db_index=True, max_length=100, unique=True, verbose_name='다날 거래 ID')),
                ('status', models.CharField(choices=[('PENDING', '대기'), ('APPROVED', '승인'), ('REJECTED', '거절'), ('CANCELLED', '취소')], default='PENDING', max_length=20, verbose_name='결제 상태')),
                ('danal_response', models.JSONField(blank=True, default=dict, verbose_name='다날 API 응답')),
                ('mysql_synced', models.BooleanField(default=False, verbose_name='MySQL 동기화 여부')),
                ('error_code', models.CharField(blank=True, max_length=10, verbose_name='오류 코드')),
                ('error_message', models.TextField(blank=True, verbose_name='오류 메시지')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '결제 내역',
                'verbose_name_plural': '결제 내역',
                'db_table': 'payment_paymenthistory',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['member', 'created_at'], name='member_created_idx'),
                    models.Index(fields=['danal_order_id'], name='danal_order_id_idx'),
                    models.Index(fields=['tid'], name='tid_idx'),
                    models.Index(fields=['status'], name='status_idx'),
                ],
            },
        ),
    ]
