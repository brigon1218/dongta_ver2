"""
결제 비즈니스 로직 서비스 레이어
View와 DanalClient 사이에서 비즈니스 로직을 처리합니다.
"""
import logging
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from .models import PaymentHistory, PointAccount, PaymentStatus
from .danal.client import DanalClient, DanalResponse
from .tasks import sync_payment_to_mysql

logger = logging.getLogger(__name__)


class PaymentService:
    """결제 비즈니스 로직을 담당하는 서비스 클래스"""

    @staticmethod
    def initiate_danal_payment(member, amount: int, pay_method: str, order_id: str) -> tuple[PaymentHistory, DanalResponse]:
        """
        다날 결제를 초기화하고 결제 세션을 생성합니다.

        Args:
            member: 결제자 (User)
            amount: 결제 금액 (원)
            pay_method: 결제 수단
            order_id: 가맹점 주문 ID

        Returns:
            (PaymentHistory, DanalResponse): 결제 내역과 다날 응답

        Raises:
            ValueError: 유효하지 않은 파라미터
        """
        if amount < 1000:
            raise ValueError("Minimum payment amount is 1,000 KRW")

        # 1. 결제 내역 사전 생성 (PENDING)
        payment = PaymentHistory.objects.create(
            member=member,
            amount=amount,
            point_amount=amount,
            pay_method=pay_method,
            status=PaymentStatus.PENDING,
            danal_order_id=order_id,
        )

        # 2. 다날 API 호출 (READY)
        client = DanalClient()
        response = client.ready(
            order_id=order_id,
            amount=amount,
            item_name=f"동타포인트 {amount}P 충전",
            user_id=member.username,
            return_url=settings.DANAL_RETURN_URL,
            cancel_url=settings.DANAL_RETURN_URL
        )

        # 3. 응답 처리
        if response.is_success:
            payment.tid = response.get('TID')
            payment.save(update_fields=['tid'])
            logger.info(f"Payment {payment.id} initiated with TID {payment.tid}")
        else:
            payment.status = PaymentStatus.REJECTED
            payment.result_code = response.return_code
            payment.result_message = response.return_msg
            payment.save(update_fields=['status', 'result_code', 'result_message'])
            logger.error(f"Payment {payment.id} READY failed: {response.return_msg}")

        return payment, response

    @staticmethod
    def approve_danal_payment(payment: PaymentHistory) -> DanalResponse:
        """
        다날 결제를 최종 승인합니다.

        Args:
            payment: PaymentHistory 객체

        Returns:
            DanalResponse: 다날 서버 응답

        Side Effects:
            - PaymentHistory 상태 업데이트
            - PointAccount 포인트 적립
            - Celery Task 발행 (MySQL 동기화)
        """
        client = DanalClient()
        response = client.approve(tid=payment.tid)

        with transaction.atomic():
            payment.result_code = response.return_code
            payment.result_message = response.return_msg
            payment.is_success = response.is_success
            payment.status = PaymentStatus.APPROVED if response.is_success else PaymentStatus.REJECTED
            payment.danal_response = response.raw

            if response.is_success:
                payment.confirmed_at = timezone.now()

            payment.save(update_fields=[
                'result_code', 'result_message', 'is_success',
                'status', 'confirmed_at', 'danal_response'
            ])

            # 포인트 적립 (승인 시에만)
            if response.is_success:
                point_account, _ = PointAccount.objects.select_for_update().get_or_create(
                    member=payment.member
                )
                point_account.total_charged += payment.point_amount
                point_account.last_charged_at = timezone.now()
                point_account.save(update_fields=['total_charged', 'last_charged_at'])
                logger.info(f"Payment {payment.id} approved. Points {payment.point_amount} credited to {payment.member.username}")

                # MySQL 동기화 태스크 발행
                sync_payment_to_mysql.delay(payment.id)
            else:
                logger.error(f"Payment {payment.id} approval failed: {response.return_msg}")

        return response

    @staticmethod
    def cancel_danal_payment(payment: PaymentHistory, reason: str) -> DanalResponse:
        """
        다날 결제를 취소합니다.

        Args:
            payment: PaymentHistory 객체
            reason: 취소 사유

        Returns:
            DanalResponse: 다날 서버 응답

        Side Effects:
            - PaymentHistory 상태를 CANCELLED로 업데이트
            - PointAccount 포인트 차감
        """
        if payment.status != PaymentStatus.APPROVED:
            raise ValueError("Only approved payments can be cancelled")

        client = DanalClient()
        response = client.cancel(tid=payment.tid, amount=payment.amount, reason=reason)

        if response.is_success:
            with transaction.atomic():
                point_account = PointAccount.objects.select_for_update().get(member=payment.member)

                # 포인트 사용 여부 확인 (사용되지 않은 경우만 취소 가능)
                if point_account.balance < payment.point_amount:
                    raise ValueError(f"Cannot cancel: {payment.point_amount} points already used")

                point_account.total_charged -= payment.point_amount
                point_account.save(update_fields=['total_charged'])

                payment.status = PaymentStatus.CANCELLED
                payment.result_message = f"취소완료: {reason}"
                payment.save(update_fields=['status', 'result_message'])
                logger.info(f"Payment {payment.id} cancelled. {payment.point_amount} points refunded to {payment.member.username}")
        else:
            logger.error(f"Payment {payment.id} cancellation failed: {response.return_msg}")

        return response

    @staticmethod
    def use_points(member, amount: int, description: str = '서비스 사용') -> PointAccount:
        """
        사용자 포인트를 차감합니다.

        Args:
            member: User 객체
            amount: 차감 금액
            description: 사용 설명

        Returns:
            PointAccount: 업데이트된 포인트 계정

        Raises:
            ValueError: 포인트 부족
        """
        with transaction.atomic():
            point_account, _ = PointAccount.objects.select_for_update().get_or_create(
                member=member
            )

            if point_account.balance < amount:
                raise ValueError(f"Insufficient points: balance={point_account.balance}, required={amount}")

            point_account.total_used += amount
            point_account.last_used_at = timezone.now()
            point_account.save(update_fields=['total_used', 'last_used_at'])
            logger.info(f"{amount} points used by {member.username}: {description}")

        return point_account
