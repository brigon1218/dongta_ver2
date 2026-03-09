from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from core.models import BaseModel


class MemberManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError('아이디는 필수입니다.')
        if not email:
            raise ValueError('이메일은 필수입니다.')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)  # Argon2id 해싱 (Django 기본)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('level', 1)
        return self.create_user(username, email, password, **extra_fields)


class Member(AbstractBaseUser, PermissionsMixin, BaseModel):
    """
    회원 모델 (MySQL: TBL_MEMB 마이그레이션 대상)
    패스워드: Argon2id (PHP의 md5 대체)
    """
    username = models.CharField(max_length=50, unique=True, verbose_name='아이디')
    name = models.CharField(max_length=50, verbose_name='이름')
    email = models.EmailField(unique=True, verbose_name='이메일')
    level = models.SmallIntegerField(default=9, verbose_name='회원등급')  # 9=일반, 1=관리자

    # 연락처 (PHP: memb_hp1~3, memb_tel1~4 → 통합)
    phone = models.CharField(max_length=20, blank=True, verbose_name='휴대폰')
    landline = models.CharField(max_length=20, blank=True, verbose_name='일반전화')

    # 주소 (PHP: memb_post1+2, memb_addr1+2 → 통합)
    postal_code = models.CharField(max_length=10, blank=True, verbose_name='우편번호')
    address = models.CharField(max_length=200, blank=True, verbose_name='주소')

    region = models.CharField(max_length=50, blank=True, verbose_name='지역')
    corp_name = models.CharField(max_length=100, blank=True, verbose_name='회사명')
    member_type = models.CharField(max_length=20, blank=True, verbose_name='회원유형')
    member_class = models.CharField(max_length=20, blank=True, verbose_name='회원분류')

    point = models.IntegerField(default=0, verbose_name='포인트')
    email_opt_in = models.BooleanField(default=True, verbose_name='이메일수신동의')
    is_overseas = models.BooleanField(default=False, verbose_name='해외거주')
    overseas_approved = models.BooleanField(default=False, verbose_name='해외거주승인')

    last_login_at = models.DateTimeField(null=True, blank=True, verbose_name='마지막로그인')
    login_count = models.IntegerField(default=0, verbose_name='로그인횟수')
    want_quit = models.BooleanField(default=False, verbose_name='탈퇴희망')
    quit_reason = models.TextField(blank=True, verbose_name='탈퇴사유')
    memo = models.TextField(blank=True, verbose_name='메모')
    reg_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='가입IP')

    # 소셜 로그인 (MySQL: Google_Member, Naver_Member → 통합)
    google_id = models.CharField(max_length=200, blank=True, unique=True,
                                  null=True, verbose_name='구글ID')
    naver_id = models.CharField(max_length=200, blank=True, unique=True,
                                 null=True, verbose_name='네이버ID')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = MemberManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'name']

    class Meta:
        db_table = 'accounts_member'
        verbose_name = '회원'
        verbose_name_plural = '회원 목록'
        indexes = [
            models.Index(fields=['username'], name='idx_member_username'),
            models.Index(fields=['email'], name='idx_member_email'),
            models.Index(fields=['region'], name='idx_member_region'),
        ]

    def __str__(self):
        return f'{self.username} ({self.name})'


class MemberDormant(BaseModel):
    """휴면 회원 (MySQL: TBL_MEMB_DORM)"""
    member = models.OneToOneField(
        Member,
        on_delete=models.CASCADE,
        related_name='dormant_info',
        verbose_name='회원'
    )
    dormant_since = models.DateField(verbose_name='휴면전환일')
    original_data = models.JSONField(verbose_name='원본데이터')  # 복구용

    class Meta:
        db_table = 'accounts_member_dormant'
        verbose_name = '휴면회원'
