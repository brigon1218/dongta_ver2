# Generated migration for business114 app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.indexes


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Business',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False, verbose_name='삭제여부')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성일시')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정일시')),
                ('business_type', models.SmallIntegerField(
                    choices=[(1, '공장'), (2, '매장')],
                    verbose_name='업체유형'
                )),
                ('corp_name', models.CharField(max_length=100, verbose_name='업체명')),
                ('phone', models.CharField(blank=True, max_length=30, verbose_name='전화번호')),
                ('fax', models.CharField(blank=True, max_length=30, verbose_name='팩스')),
                ('homepage', models.URLField(blank=True, verbose_name='홈페이지')),
                ('postal_code', models.CharField(blank=True, max_length=10, verbose_name='우편번호')),
                ('address', models.CharField(max_length=200, verbose_name='주소')),
                ('industry_type', models.SmallIntegerField(default=0, verbose_name='업종')),
                ('items', models.JSONField(default=list, verbose_name='취급품목')),
                ('location_info', models.TextField(blank=True, verbose_name='위치정보')),
                ('keywords', models.CharField(blank=True, max_length=500, verbose_name='키워드')),
                ('description', models.TextField(blank=True, verbose_name='업체설명')),
                ('logo_image', models.CharField(blank=True, max_length=500, verbose_name='로고이미지')),
                ('view_count', models.IntegerField(default=0, verbose_name='조회수')),
                ('total_payment', models.IntegerField(default=0, verbose_name='총결제금액')),
                ('payment_method', models.CharField(blank=True, max_length=50, verbose_name='결제방법')),
                ('approval_no', models.CharField(blank=True, max_length=100, verbose_name='승인번호')),
                ('is_approved', models.BooleanField(default=False, verbose_name='승인여부')),
                ('member', models.ForeignKey(
                    null=True,
                    blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='businesses',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='회원'
                )),
            ],
            options={
                'verbose_name': '업체(동타114)',
                'verbose_name_plural': '업체(동타114) 목록',
                'db_table': 'business114_business',
            },
        ),
        migrations.AddIndex(
            model_name='business',
            index=models.Index(fields=['industry_type'], name='idx_business_industry_type'),
        ),
        migrations.AddIndex(
            model_name='business',
            index=models.Index(fields=['is_approved', 'is_deleted'], name='idx_business_approved_deleted'),
        ),
        migrations.AddIndex(
            model_name='business',
            index=models.Index(fields=['corp_name'], name='idx_business_corp_name'),
        ),
        migrations.AddIndex(
            model_name='business',
            index=django.contrib.postgres.indexes.GinIndex(fields=['items'], name='idx_business_items_gin'),
        ),
    ]
