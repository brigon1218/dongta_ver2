from django.db import models
from core.models import BaseModel


class PointAccount(models.Model):
    """
    동타포인트 계정 (MySQL: DongtaPointMain 마이그레이션 대상)
    """
    member = models.OneToOneField(
        'accounts.Member',
        on_delete=models.CASCADE,
        related_name='point_account',
        verbose_name='회원'
    )
    total_charged = models.BigIntegerField(default=0, verbose_name='총충전포인트')   # nTotalChargeDP
    total_used = models.BigIntegerField(default=0, verbose_name='총사용포인트')      # nTotalUseDP
    last_charged_at = models.DateTimeField(null=True, blank=True, verbose_name='마지막충전일시')
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name='마지막사용일시')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')

    @property
    def balance(self):
        """현재 잔액 = 총충전 - 총사용"""
        return self.total_charged - self.total_used

    class Meta:
        db_table = 'payment_pointaccount'
        verbose_name = '포인트계정'
        verbose_name_plural = '포인트계정 목록'

    def __str__(self):
        return f'{self.member.username} 포인트 (잔액: {self.balance})'


class PaymentStatus(models.TextChoices):
    PENDING = 'pending', '대기'
    APPROVED = 'approved', '승인'
    REJECTED = 'rejected', '거절'
    CANCELLED = 'cancelled', '취소'


class PaymentHistory(BaseModel):
    """
    결제 내역 (MySQL: DongtaPointCharge 마이그레이션 대상)
    """
    class PayMethod(models.TextChoices):
        CARD = 'card', '카드'
        BANK_TRANSFER = 'bank', '무통장입금'
        DIRECT_BANK = 'direct_bank', '실시간계좌이체'

    id = models.BigAutoField(primary_key=True)
    member = models.ForeignKey(
        'accounts.Member',
        on_delete=models.CASCADE,
        related_name='payment_histories',
        verbose_name='회원'
    )
    amount = models.IntegerField(verbose_name='결제금액')                                    # nChargePrice (원)
    point_amount = models.IntegerField(verbose_name='충전포인트')                            # nChargeDP
    pay_method = models.CharField(
        max_length=30,
        choices=PayMethod.choices,
        verbose_name='결제방법'
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        verbose_name='결제상태'
    )
    is_success = models.BooleanField(default=False, verbose_name='성공여부')
    result_code = models.CharField(max_length=50, blank=True, verbose_name='결과코드')
    result_message = models.CharField(max_length=200, blank=True, verbose_name='결과메시지')
    
    # 다날 연동 필드
    tid = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        verbose_name='다날거래번호(TID)',
        db_index=True
    )
    danal_order_id = models.CharField(
        max_length=100,
        blank=True,
        unique=True,
        null=True,
        verbose_name='다날주문번호'
    )
    danal_response = models.JSONField(
        null=True,
        blank=True,
        verbose_name='다날원본응답'
    )
    mysql_synced = models.BooleanField(
        default=False,
        verbose_name='MySQL동기화여부'
    )
    error_code = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='에러코드'
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='에러메시지'
    )
    
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='승인일시')

    class Meta:
        db_table = 'payment_paymenthistory'
        verbose_name = '결제내역'
        verbose_name_plural = '결제내역 목록'
        indexes = [
            models.Index(fields=['member', 'is_success'], name='idx_payment_member_success'),
            models.Index(fields=['danal_order_id'], name='idx_payment_danal_order'),
        ]

    def __str__(self):
        return f'{self.member.username} {self.amount}원 ({self.get_pay_method_display()})'
