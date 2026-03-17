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
            name='MyFolder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated at')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='Is deleted')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted at')),
                ('name', models.CharField(max_length=100, verbose_name='폴더명')),
                ('description', models.TextField(blank=True, verbose_name='폴더설명')),
                ('member', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='my_folders',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='회원'
                )),
            ],
            options={
                'verbose_name': '찜폴더',
                'verbose_name_plural': '찜폴더 목록',
                'db_table': 'mypage_my_folder',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MyData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated at')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='Is deleted')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted at')),
                ('content_type', models.CharField(
                    choices=[('business', '동타114 업체'), ('recruit', '채용공고'), ('board', '게시글')],
                    max_length=30,
                    verbose_name='컨텐츠유형'
                )),
                ('object_id', models.BigIntegerField(verbose_name='대상 PK')),
                ('memo', models.TextField(blank=True, verbose_name='메모')),
                ('folder', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='mypage.myfolder',
                    verbose_name='폴더'
                )),
                ('member', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='my_data',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='회원'
                )),
            ],
            options={
                'verbose_name': '찜항목',
                'verbose_name_plural': '찜항목 목록',
                'db_table': 'mypage_my_data',
            },
        ),
        migrations.AddIndex(
            model_name='mydata',
            index=models.Index(fields=['member', 'content_type'], name='idx_mydata_member_type'),
        ),
        migrations.AddIndex(
            model_name='mydata',
            index=models.Index(fields=['folder', 'content_type'], name='idx_mydata_folder_type'),
        ),
        migrations.AlterUniqueTogether(
            name='mydata',
            unique_together={('folder', 'content_type', 'object_id')},
        ),
    ]
