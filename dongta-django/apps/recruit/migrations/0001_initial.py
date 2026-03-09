# Generated migration for recruit app

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
            name='Company',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False, verbose_name='삭제여부')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성일시')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정일시')),
                ('company_name', models.CharField(max_length=100, verbose_name='회사명')),
                ('phone', models.CharField(blank=True, max_length=30, verbose_name='전화번호')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='이메일')),
                ('homepage', models.URLField(blank=True, verbose_name='홈페이지')),
                ('postal_code', models.CharField(blank=True, max_length=10, verbose_name='우편번호')),
                ('address', models.CharField(blank=True, max_length=200, verbose_name='주소')),
                ('introduction', models.TextField(blank=True, verbose_name='회사소개')),
                ('has_notice', models.BooleanField(default=False, verbose_name='공고등록여부')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='companies', to=settings.AUTH_USER_MODEL, verbose_name='회원')),
            ],
            options={
                'verbose_name': '채용회사',
                'verbose_name_plural': '채용회사 목록',
                'db_table': 'recruit_company',
            },
        ),
        migrations.CreateModel(
            name='JobNotice',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False, verbose_name='삭제여부')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성일시')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정일시')),
                ('employment_type', models.CharField(max_length=50, verbose_name='고용형태')),
                ('title', models.CharField(max_length=200, verbose_name='공고제목')),
                ('occupations', models.JSONField(default=list, verbose_name='모집직종')),
                ('career_required', models.BooleanField(default=False, verbose_name='경력필요')),
                ('is_approved', models.BooleanField(default=False, verbose_name='승인여부')),
                ('approval_no', models.CharField(blank=True, max_length=100, verbose_name='승인번호')),
                ('payment_code', models.CharField(blank=True, max_length=100, verbose_name='결제코드')),
                ('is_premium', models.BooleanField(default=False, verbose_name='프리미엄여부')),
                ('premium_start_date', models.DateField(blank=True, null=True, verbose_name='프리미엄시작일')),
                ('premium_end_date', models.DateField(blank=True, null=True, verbose_name='프리미엄종료일')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_notices', to='recruit.company', verbose_name='회사')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_notices', to=settings.AUTH_USER_MODEL, verbose_name='회원')),
            ],
            options={
                'verbose_name': '채용공고',
                'verbose_name_plural': '채용공고 목록',
                'db_table': 'recruit_job_notice',
            },
        ),
        migrations.CreateModel(
            name='JobSeeker',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False, verbose_name='삭제여부')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성일시')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정일시')),
                ('name', models.CharField(max_length=50, verbose_name='이름')),
                ('birth_date', models.DateField(blank=True, null=True, verbose_name='생년월일')),
                ('gender', models.CharField(blank=True, max_length=10, verbose_name='성별')),
                ('phone', models.CharField(blank=True, max_length=20, verbose_name='전화번호')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='이메일')),
                ('address', models.CharField(blank=True, max_length=200, verbose_name='주소')),
                ('profile_image', models.CharField(blank=True, max_length=500, verbose_name='프로필이미지')),
                ('resume_registered', models.BooleanField(default=False, verbose_name='이력서등록여부')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_seekers', to=settings.AUTH_USER_MODEL, verbose_name='회원')),
            ],
            options={
                'verbose_name': '구직자',
                'verbose_name_plural': '구직자 목록',
                'db_table': 'recruit_job_seeker',
            },
        ),
        migrations.AddIndex(
            model_name='jobnotice',
            index=models.Index(fields=['is_approved', 'is_deleted'], name='idx_jobnotice_approved_deleted'),
        ),
        migrations.AddIndex(
            model_name='jobnotice',
            index=models.Index(fields=['premium_end_date'], name='idx_jobnotice_premium_end'),
        ),
        migrations.AddIndex(
            model_name='jobnotice',
            index=django.contrib.postgres.indexes.GinIndex(fields=['occupations'], name='idx_jobnotice_occ_gin'),
        ),
    ]
