import logging
from celery import shared_task
from django.db import connections
from django.utils import timezone
from .models import PaymentHistory

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def sync_payment_to_mysql(self, payment_id: int):
    """
    결제 내역을 레거시 MySQL(DongtaPointCharge)에 이중 기록한다.
    하이브리드 운영 기간 동안 레거시 시스템의 포인트 기능을 유지하기 위함.
    """
    try:
        payment = PaymentHistory.objects.get(pk=payment_id)
        
        # 이미 동기화된 경우 스킵
        if payment.mysql_synced:
            logger.info(f"Payment {payment_id} already synced to MySQL.")
            return True

        # 레거시 데이터베이스 연결 (settings/base.py의 'legacy' 설정 참고)
        # MySQL 컬럼 매핑:
        # nMembIdx        → member_id
        # nChargePrice    → amount
        # nChargeDP       → point_amount
        # vcPayMethod     → pay_method (정규화 필요할 수 있음)
        # bSuccess        → is_success (1/0)
        # vcPayResultCode → result_code
        # vcPayResultMsg  → result_message
        # sOrderId        → danal_order_id
        # dRegDate        → created_at.date()
        # tRegTime        → created_at.time()

        with connections['legacy'].cursor() as cursor:
            # 레거시 테이블명: DongtaPointCharge
            sql = """
                INSERT INTO DongtaPointCharge 
                (nMembIdx, nChargePrice, nChargeDP, vcPayMethod, bSuccess, 
                 vcPayResultCode, vcPayResultMsg, sOrderId, dRegDate, tRegTime)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            created_at = payment.created_at or timezone.now()
            
            cursor.execute(sql, [
                payment.member_id,
                payment.amount,
                payment.point_amount,
                payment.pay_method[:20],  # 컬럼 길이 제한 방어
                1 if payment.is_success else 0,
                payment.result_code[:50],
                payment.result_message[:200],
                payment.danal_order_id[:100],
                created_at.date(),
                created_at.time(),
            ])
            
        # 성공 시 동기화 여부 업데이트
        payment.mysql_synced = True
        payment.save(update_fields=['mysql_synced'])
        
        logger.info(f"Successfully synced payment {payment_id} to MySQL.")
        return True

    except PaymentHistory.DoesNotExist:
        logger.error(f"Payment {payment_id} not found for MySQL sync.")
        return False
        
    except Exception as exc:
        logger.exception(f"Error syncing payment {payment_id} to MySQL. Retrying...")
        # 지수 백오프로 재시도 (60초 * 2^retries)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
