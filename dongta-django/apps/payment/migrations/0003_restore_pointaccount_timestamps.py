"""
PointAccount에 created_at, updated_at 필드 복구.
0002 마이그레이션에서 제거됐으나 DB에 컬럼이 남아 있어 IntegrityError 발생.
DB에 컬럼이 이미 존재하므로 서버에서는 --fake 옵션으로 실행 필요.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0002_alter_paymenthistory_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='pointaccount',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='생성일시'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pointaccount',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='수정일시'),
        ),
    ]
