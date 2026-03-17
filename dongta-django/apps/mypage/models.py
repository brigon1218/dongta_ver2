from django.db import models
from core.models import BaseModel


class MyFolder(BaseModel):
    """
    사용자의 찜 폴더 (북마크 그룹)
    Design S3.6: MyFolder 모델
    """
    member = models.ForeignKey(
        'accounts.Member',
        on_delete=models.CASCADE,
        related_name='my_folders',
        verbose_name='회원'
    )
    name = models.CharField(max_length=100, verbose_name='폴더명')
    description = models.TextField(blank=True, verbose_name='폴더설명')

    class Meta:
        db_table = 'mypage_my_folder'
        verbose_name = '찜폴더'
        verbose_name_plural = '찜폴더 목록'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.member.username} - {self.name}'


class MyData(BaseModel):
    """
    찜한 항목들 (업체, 채용공고 등을 폴더에 저장)
    Design S3.6: MyData 모델
    content_type: 'business' | 'recruit' | 'board'
    object_id: 해당 컨텐츠의 PK
    """
    CONTENT_TYPE_CHOICES = [
        ('business', '동타114 업체'),
        ('recruit', '채용공고'),
        ('board', '게시글'),
    ]

    folder = models.ForeignKey(
        MyFolder,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='폴더'
    )
    member = models.ForeignKey(
        'accounts.Member',
        on_delete=models.CASCADE,
        related_name='my_data',
        verbose_name='회원'
    )
    content_type = models.CharField(
        max_length=30,
        choices=CONTENT_TYPE_CHOICES,
        verbose_name='컨텐츠유형'
    )
    object_id = models.BigIntegerField(verbose_name='대상 PK')
    memo = models.TextField(blank=True, verbose_name='메모')

    class Meta:
        db_table = 'mypage_my_data'
        verbose_name = '찜항목'
        verbose_name_plural = '찜항목 목록'
        unique_together = [('folder', 'content_type', 'object_id')]
        indexes = [
            models.Index(fields=['member', 'content_type'], name='idx_mydata_member_type'),
            models.Index(fields=['folder', 'content_type'], name='idx_mydata_folder_type'),
        ]

    def __str__(self):
        return f'{self.folder.name} - {self.content_type}:{self.object_id}'
