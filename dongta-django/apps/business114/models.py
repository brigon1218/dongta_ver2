from django.db import models
from django.contrib.postgres.indexes import GinIndex
from core.models import BaseModel


class BusinessType(models.IntegerChoices):
    FACTORY = 1, '공장'
    STORE = 2, '매장'


class Business(BaseModel):
    """
    동타114 업체 (MySQL: TBL_YELLOW 마이그레이션 대상)
    """
    id = models.BigAutoField(primary_key=True)
    member = models.ForeignKey(
        'accounts.Member',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='businesses',
        verbose_name='회원'
    )
    business_type = models.SmallIntegerField(
        choices=BusinessType.choices,
        verbose_name='업체유형'
    )                                                               # yellow_class
    corp_name = models.CharField(max_length=100, verbose_name='업체명')    # yellow_corpname
    phone = models.CharField(max_length=30, blank=True, verbose_name='전화번호')  # yellow_tel
    fax = models.CharField(max_length=30, blank=True, verbose_name='팩스')        # yellow_fax
    homepage = models.URLField(blank=True, verbose_name='홈페이지')               # yellow_homepage
    postal_code = models.CharField(max_length=10, blank=True, verbose_name='우편번호')
    address = models.CharField(max_length=200, verbose_name='주소')               # yellow_addr1+addr2
    industry_type = models.SmallIntegerField(default=0, verbose_name='업종')      # yellow_type (1~8)
    items = models.JSONField(default=list, verbose_name='취급품목')               # yellow_item (1~40+)
    location_info = models.TextField(blank=True, verbose_name='위치정보')         # yellow_locainfo
    keywords = models.CharField(max_length=500, blank=True, verbose_name='키워드')  # yellow_keyword
    description = models.TextField(blank=True, verbose_name='업체설명')           # yellow_desc
    logo_image = models.CharField(max_length=500, blank=True, verbose_name='로고이미지')  # yellow_img
    view_count = models.IntegerField(default=0, verbose_name='조회수')            # yellow_hit
    total_payment = models.IntegerField(default=0, verbose_name='총결제금액')     # yellow_totpay
    payment_method = models.CharField(max_length=50, blank=True, verbose_name='결제방법')
    approval_no = models.CharField(max_length=100, blank=True, verbose_name='승인번호')  # yellow_ack_no
    is_approved = models.BooleanField(default=False, verbose_name='승인여부')     # yellow_successflag

    class Meta:
        db_table = 'business114_business'
        verbose_name = '업체(동타114)'
        verbose_name_plural = '업체(동타114) 목록'
        indexes = [
            models.Index(fields=['industry_type'], name='idx_business_industry_type'),
            models.Index(fields=['is_approved', 'is_deleted'], name='idx_business_approved_deleted'),
            models.Index(fields=['corp_name'], name='idx_business_corp_name'),
            GinIndex(fields=['items'], name='idx_business_items_gin'),
        ]

    def __str__(self):
        return f'{self.corp_name} (업종:{self.industry_type})'
