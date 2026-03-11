# Generated migration for Member model

from django.db import migrations, models
import django.db.models.deletion
import core.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Member',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated at')),
                ('username', models.CharField(max_length=50, unique=True, verbose_name='아이디')),
                ('name', models.CharField(max_length=50, verbose_name='이름')),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='이메일')),
                ('level', models.SmallIntegerField(default=9, verbose_name='회원등급')),
                ('phone', models.CharField(blank=True, max_length=20, verbose_name='휴대폰')),
                ('landline', models.CharField(blank=True, max_length=20, verbose_name='일반전화')),
                ('postal_code', models.CharField(blank=True, max_length=10, verbose_name='우편번호')),
                ('address', models.CharField(blank=True, max_length=200, verbose_name='주소')),
                ('region', models.CharField(blank=True, max_length=50, verbose_name='지역')),
                ('corp_name', models.CharField(blank=True, max_length=100, verbose_name='회사명')),
                ('member_type', models.CharField(blank=True, max_length=20, verbose_name='회원유형')),
                ('member_class', models.CharField(blank=True, max_length=20, verbose_name='회원분류')),
                ('point', models.IntegerField(default=0, verbose_name='포인트')),
                ('email_opt_in', models.BooleanField(default=True, verbose_name='이메일수신동의')),
                ('is_overseas', models.BooleanField(default=False, verbose_name='해외거주')),
                ('overseas_approved', models.BooleanField(default=False, verbose_name='해외거주승인')),
                ('last_login_at', models.DateTimeField(blank=True, null=True, verbose_name='마지막로그인')),
                ('login_count', models.IntegerField(default=0, verbose_name='로그인횟수')),
                ('want_quit', models.BooleanField(default=False, verbose_name='탈퇴희망')),
                ('quit_reason', models.TextField(blank=True, verbose_name='탈퇴사유')),
                ('memo', models.TextField(blank=True, verbose_name='메모')),
                ('reg_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='가입IP')),
                ('google_id', models.CharField(blank=True, max_length=200, null=True, unique=True, verbose_name='구글ID')),
                ('naver_id', models.CharField(blank=True, max_length=200, null=True, unique=True, verbose_name='네이버ID')),
                ('is_active', models.BooleanField(default=True)),
                ('is_staff', models.BooleanField(default=False)),
                ('is_superuser', models.BooleanField(default=False)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': '회원',
                'verbose_name_plural': '회원 목록',
                'db_table': 'accounts_member',
            },
        ),
        migrations.CreateModel(
            name='PasswordResetToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated at')),
                ('token', models.CharField(max_length=128, unique=True, verbose_name='토큰')),
                ('expires_at', models.DateTimeField(verbose_name='만료시간')),
                ('is_used', models.BooleanField(default=False, verbose_name='사용여부')),
                ('used_at', models.DateTimeField(blank=True, null=True, verbose_name='사용시간')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='password_reset_tokens', to='accounts.member', verbose_name='회원')),
            ],
            options={
                'verbose_name': '비밀번호재설정토큰',
                'db_table': 'accounts_password_reset_token',
            },
        ),
        migrations.CreateModel(
            name='MemberDormant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated at')),
                ('dormant_since', models.DateField(verbose_name='휴면전환일')),
                ('original_data', models.JSONField(verbose_name='원본데이터')),
                ('member', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='dormant_info', to='accounts.member', verbose_name='회원')),
            ],
            options={
                'verbose_name': '휴면회원',
                'db_table': 'accounts_member_dormant',
            },
        ),
        migrations.AddIndex(
            model_name='passwordresettoken',
            index=models.Index(fields=['token'], name='idx_reset_token'),
        ),
        migrations.AddIndex(
            model_name='passwordresettoken',
            index=models.Index(fields=['member'], name='idx_reset_member'),
        ),
        migrations.AddIndex(
            model_name='member',
            index=models.Index(fields=['username'], name='idx_member_username'),
        ),
        migrations.AddIndex(
            model_name='member',
            index=models.Index(fields=['email'], name='idx_member_email'),
        ),
        migrations.AddIndex(
            model_name='member',
            index=models.Index(fields=['region'], name='idx_member_region'),
        ),
    ]
