from django.db import models
from core.models import BaseModel


class PostCategory(models.TextChoices):
    NOTICE = 'NOTICE', '공지사항'
    FREE = 'FREE', '자유게시판'
    QNA = 'QNA', '질문답변'
    GALLERY = 'GALLERY', '갤러리'


class Post(BaseModel):
    """
    게시글 모델
    """
    category = models.CharField(
        max_length=20,
        choices=PostCategory.choices,
        default=PostCategory.FREE,
        verbose_name='카테고리',
        db_index=True
    )
    title = models.CharField(max_length=200, verbose_name='제목')
    content = models.TextField(verbose_name='내용')
    member = models.ForeignKey(
        'accounts.Member',
        on_delete=models.CASCADE,
        related_name='posts',
        verbose_name='작성자'
    )
    view_count = models.PositiveIntegerField(default=0, verbose_name='조회수')
    like_count = models.PositiveIntegerField(default=0, verbose_name='추천수')
    is_pinned = models.BooleanField(default=False, verbose_name='상단고정여부')

    class Meta:
        db_table = 'board_post'
        verbose_name = '게시글'
        verbose_name_plural = '게시글 목록'
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['category', '-created_at']),
        ]

    def __str__(self):
        return f'[{self.get_category_display()}] {self.title}'


class Comment(BaseModel):
    """
    댓글 모델 (1단계 대댓글 지원)
    """
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='게시글'
    )
    member = models.ForeignKey(
        'accounts.Member',
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='작성자'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name='부모댓글'
    )
    content = models.TextField(verbose_name='댓글내용')

    class Meta:
        db_table = 'board_comment'
        verbose_name = '댓글'
        verbose_name_plural = '댓글 목록'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.member.username}의 댓글'


class PostLike(models.Model):
    """
    게시글 추천(좋아요) 모델 (중복 추천 방지)
    """
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name='게시글'
    )
    member = models.ForeignKey(
        'accounts.Member',
        on_delete=models.CASCADE,
        related_name='post_likes',
        verbose_name='회원'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'board_post_like'
        unique_together = ('post', 'member')
        verbose_name = '게시글추천'
        verbose_name_plural = '게시글추천 목록'
