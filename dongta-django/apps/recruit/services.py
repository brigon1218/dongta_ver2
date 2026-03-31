from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from apps.payment.models import PointAccount
from .models import JobNotice


class RecruitService:
    """채용 정보 관련 비즈니스 로직"""

    class ProfileAlreadyExistsException(Exception):
        """이미 구직자 프로필이 존재하는 경우 발생하는 예외"""
        pass

    @staticmethod

    def apply_premium(notice_id: int, user, days: int = 30, point_cost: int = 10000):
        """
        프리미엄 채용 공고 신청 처리
        1. 잔액 확인
        2. 포인트 차감
        3. 공고 상태 업데이트 (is_premium=True 및 기간 설정)
        """
        with transaction.atomic():
            # 1. 공고 확인 및 소유권 검증
            notice = JobNotice.objects.select_for_update().get(id=notice_id, member=user, is_deleted=False)
            
            # 2. 포인트 잔액 확인
            point_account, _ = PointAccount.objects.select_for_update().get_or_create(member=user)
            if point_account.balance < point_cost:
                return False, f"포인트가 부족합니다. (잔액: {point_account.balance}P, 필요: {point_cost}P)"

            # 3. 포인트 차감
            point_account.total_used += point_cost
            point_account.last_used_at = timezone.now()
            point_account.save(update_fields=['total_used', 'last_used_at'])

            # 4. 프리미엄 기간 설정
            now = timezone.now().date()
            # 이미 프리미엄인 경우 기간 연장, 아니면 새로 시작
            if notice.is_premium and notice.premium_end_date and notice.premium_end_date >= now:
                notice.premium_end_date += timedelta(days=days)
            else:
                notice.premium_start_date = now
                notice.premium_end_date = now + timedelta(days=days)
            
            notice.is_premium = True
            notice.save(update_fields=['is_premium', 'premium_start_date', 'premium_end_date'])

            return True, notice
