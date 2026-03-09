"""
apps/sync/migrations/0001_initial.py

EventOutbox, SyncLog 초기 마이그레이션
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='EventOutbox',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False, verbose_name='PK')),
                ('event_type', models.CharField(
                    choices=[
                        ('member.insert', '회원 신규'),
                        ('member.update', '회원 수정'),
                        ('payment.insert', '결제 신규'),
                    ],
                    db_index=True,
                    max_length=50,
                    verbose_name='이벤트 유형',
                )),
                ('aggregate_type', models.CharField(
                    help_text='예: member, payment',
                    max_length=50,
                    verbose_name='집계 유형',
                )),
                ('aggregate_id', models.BigIntegerField(
                    db_index=True,
                    verbose_name='원본 레코드 PK (MySQL)',
                )),
                ('payload', models.JSONField(
                    help_text='MySQL 원본 데이터 (JSON)',
                    verbose_name='이벤트 페이로드',
                )),
                ('status', models.CharField(
                    choices=[
                        ('pending', '대기'),
                        ('processing', '처리중'),
                        ('done', '완료'),
                        ('failed', '실패'),
                        ('dead_letter', '최종실패(DLQ)'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20,
                    verbose_name='처리 상태',
                )),
                ('retry_count', models.SmallIntegerField(default=0, verbose_name='재시도 횟수')),
                ('max_retries', models.SmallIntegerField(default=3, verbose_name='최대 재시도 횟수')),
                ('error_message', models.TextField(blank=True, verbose_name='오류 메시지')),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    verbose_name='생성일시',
                )),
                ('processed_at', models.DateTimeField(
                    blank=True,
                    null=True,
                    verbose_name='처리완료일시',
                )),
            ],
            options={
                'verbose_name': '이벤트 아웃박스',
                'verbose_name_plural': '이벤트 아웃박스 목록',
                'db_table': 'sync_event_outbox',
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='SyncLog',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('task_id', models.CharField(
                    db_index=True,
                    max_length=100,
                    verbose_name='Celery Task ID',
                )),
                ('started_at', models.DateTimeField(auto_now_add=True, verbose_name='시작일시')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='완료일시')),
                ('result', models.CharField(
                    choices=[
                        ('success', '성공'),
                        ('partial', '부분성공'),
                        ('failure', '실패'),
                    ],
                    max_length=20,
                    verbose_name='결과',
                )),
                ('processed_count', models.IntegerField(default=0, verbose_name='처리건수')),
                ('failed_count', models.IntegerField(default=0, verbose_name='실패건수')),
                ('detail', models.TextField(blank=True, verbose_name='상세 로그')),
            ],
            options={
                'verbose_name': '동기화 이력',
                'verbose_name_plural': '동기화 이력 목록',
                'db_table': 'sync_log',
                'ordering': ['-started_at'],
            },
        ),
        migrations.AddIndex(
            model_name='eventoutbox',
            index=models.Index(
                fields=['status', 'created_at'],
                name='idx_outbox_status_created',
            ),
        ),
        migrations.AddIndex(
            model_name='eventoutbox',
            index=models.Index(
                fields=['event_type', 'aggregate_id'],
                name='idx_outbox_type_aggregate',
            ),
        ),
    ]
