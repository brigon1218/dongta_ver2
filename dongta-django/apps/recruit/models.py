from django.db import models
from django.contrib.postgres.indexes import GinIndex
from core.models import BaseModel


class Company(BaseModel):
    """
    채용 회사 (MySQL: TBL_JOBOFFER 마이그레이션 대상)
    """
    id = models.BigAutoField(primary_key=True)
    member = models.ForeignKey(
        'accounts.Member',
        on_delete=models.CASCADE,
        related_name='companies',
        verbose_name='회원'
    )
    company_name = models.CharField(max_length=100, verbose_name='회사명')   # offer_name
    phone = models.CharField(max_length=30, blank=True, verbose_name='전화번호')
    email = models.EmailField(blank=True, verbose_name='이메일')
    homepage = models.URLField(blank=True, verbose_name='홈페이지')
    postal_code = models.CharField(max_length=10, blank=True, verbose_name='우편번호')
    address = models.CharField(max_length=200, blank=True, verbose_name='주소')
    introduction = models.TextField(blank=True, verbose_name='회사소개')     # offer_introduce
    has_notice = models.BooleanField(default=False, verbose_name='공고등록여부')  # offer_noticeflag

    class Meta:
        db_table = 'recruit_company'
        verbose_name = '채용회사'
        verbose_name_plural = '채용회사 목록'

    def __str__(self):
        return self.company_name


class JobNotice(BaseModel):
    """
    채용 공고 (MySQL: TBL_JOBNOTICE 마이그레이션 대상)
    """
    id = models.BigAutoField(primary_key=True)
    member = models.ForeignKey(
        'accounts.Member',
        on_delete=models.CASCADE,
        related_name='job_notices',
        verbose_name='회원'
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='job_notices',
        verbose_name='회사'
    )
    employment_type = models.CharField(max_length=50, verbose_name='고용형태')   # notice_kind
    title = models.CharField(max_length=200, verbose_name='공고제목')            # notice_title
    occupations = models.JSONField(default=list, verbose_name='모집직종')        # notice_occupation (| 구분 → JSON)
    career_required = models.BooleanField(default=False, verbose_name='경력필요')
    is_approved = models.BooleanField(default=False, verbose_name='승인여부')
    approval_no = models.CharField(max_length=100, blank=True, verbose_name='승인번호')
    payment_code = models.CharField(max_length=100, blank=True, verbose_name='결제코드')
    # 프리미엄 채용
    is_premium = models.BooleanField(default=False, verbose_name='프리미엄여부')
    premium_start_date = models.DateField(null=True, blank=True, verbose_name='프리미엄시작일')
    premium_end_date = models.DateField(null=True, blank=True, verbose_name='프리미엄종료일')

    class Meta:
        db_table = 'recruit_job_notice'
        verbose_name = '채용공고'
        verbose_name_plural = '채용공고 목록'
        indexes = [
            models.Index(fields=['is_approved', 'is_deleted'], name='idx_jobnotice_approved_deleted'),
            models.Index(fields=['premium_end_date'], name='idx_jobnotice_premium_end'),
            GinIndex(fields=['occupations'], name='idx_jobnotice_occ_gin'),
        ]

    def __str__(self):
        return f'{self.title} ({self.company.company_name})'


class JobSeeker(BaseModel):
    """
    구직자 이력서 (MySQL: TBL_JOBHUNTER 마이그레이션 대상)
    """
    id = models.BigAutoField(primary_key=True)
    member = models.ForeignKey(
        'accounts.Member',
        on_delete=models.CASCADE,
        related_name='job_seekers',
        verbose_name='회원'
    )
    name = models.CharField(max_length=50, verbose_name='이름')
    birth_date = models.DateField(null=True, blank=True, verbose_name='생년월일')
    gender = models.CharField(max_length=10, blank=True, verbose_name='성별')
    phone = models.CharField(max_length=20, blank=True, verbose_name='전화번호')
    email = models.EmailField(blank=True, verbose_name='이메일')
    address = models.CharField(max_length=200, blank=True, verbose_name='주소')
    profile_image = models.CharField(max_length=500, blank=True, verbose_name='프로필이미지')
    resume_registered = models.BooleanField(default=False, verbose_name='이력서등록여부')

    class Meta:
        db_table = 'recruit_job_seeker'
        verbose_name = '구직자'
        verbose_name_plural = '구직자 목록'

    def __str__(self):
        return f'{self.name} ({self.member.username})'
