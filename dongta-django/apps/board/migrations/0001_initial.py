# Generated migration for board app

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
            name='Post',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False, verbose_name='삭제여부')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성일시')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정일시')),
                ('category', models.CharField(
                    choices=[('NOTICE', '공지사항'), ('FREE', '자유게시판'), ('QNA', '질문답변'), ('GALLERY', '갤러리')],
                    db_index=True,
                    default='FREE',
                    max_length=20,
                    verbose_name='카테고리'
                )),
                ('title', models.CharField(max_length=200, verbose_name='제목')),
                ('content', models.TextField(verbose_name='내용')),
                ('view_count', models.PositiveIntegerField(default=0, verbose_name='조회수')),
                ('like_count', models.PositiveIntegerField(default=0, verbose_name='추천수')),
                ('is_pinned', models.BooleanField(default=False, verbose_name='상단고정여부')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='posts', to=settings.AUTH_USER_MODEL, verbose_name='작성자')),
            ],
            options={
                'verbose_name': '게시글',
                'verbose_name_plural': '게시글 목록',
                'db_table': 'board_post',
            },
        ),
        migrations.CreateModel(
            name='PostLike',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='post_likes', to=settings.AUTH_USER_MODEL, verbose_name='회원')),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='likes', to='board.post', verbose_name='게시글')),
            ],
            options={
                'verbose_name': '게시글추천',
                'verbose_name_plural': '게시글추천 목록',
                'db_table': 'board_post_like',
            },
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('is_deleted', models.BooleanField(default=False, verbose_name='삭제여부')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성일시')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정일시')),
                ('content', models.TextField(verbose_name='댓글내용')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to=settings.AUTH_USER_MODEL, verbose_name='작성자')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='board.comment', verbose_name='부모댓글')),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='board.post', verbose_name='게시글')),
            ],
            options={
                'verbose_name': '댓글',
                'verbose_name_plural': '댓글 목록',
                'db_table': 'board_comment',
            },
        ),
        migrations.AddIndex(
            model_name='post',
            index=models.Index(fields=['category', '-created_at'], name='idx_post_category_created'),
        ),
        migrations.AddConstraint(
            model_name='postlike',
            constraint=models.UniqueConstraint(fields=['post', 'member'], name='unique_post_like'),
        ),
    ]
