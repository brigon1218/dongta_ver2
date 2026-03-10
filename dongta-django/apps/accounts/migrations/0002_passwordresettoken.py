# Generated migration for PasswordResetToken model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PasswordResetToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성시간')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정시간')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='삭제여부')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='삭제시간')),
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
        migrations.AddIndex(
            model_name='passwordresettoken',
            index=models.Index(fields=['token'], name='idx_reset_token'),
        ),
        migrations.AddIndex(
            model_name='passwordresettoken',
            index=models.Index(fields=['member'], name='idx_reset_member'),
        ),
    ]
