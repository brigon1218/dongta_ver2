"""
apps/sync/migrations/0002_eventsource_fields.py

Phase 2.1: EventOutbox에 source, correlation_id 필드 추가
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sync', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventoutbox',
            name='source',
            field=models.CharField(
                choices=[
                    ('django', 'Django 시스템'),
                    ('mysql', 'MySQL 레거시 시스템'),
                ],
                db_index=True,
                default='mysql',
                max_length=20,
                verbose_name='이벤트 발생 시스템',
            ),
        ),
        migrations.AddField(
            model_name='eventoutbox',
            name='correlation_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='요청 추적을 위한 X-Request-ID',
                max_length=100,
                verbose_name='상관 ID (추적용)',
            ),
        ),
    ]
