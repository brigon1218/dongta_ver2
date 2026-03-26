"""
recruit 앱 Signal 핸들러
- JobNotice 생성/수정/삭제 시 캐시 무효화
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import JobNotice, Company


@receiver(post_save, sender=JobNotice)
def invalidate_recruit_cache_on_save(sender, instance, created, **kwargs):
    """
    JobNotice 생성/수정 시 캐시 무효화
    - delete_pattern()으로 URL 기반 캐시 패턴 전체 삭제
    """
    try:
        # @cache_page 는 해시된 키를 사용하므로 delete_pattern()으로 와일드카드 삭제
        cache.delete_pattern('*recruit*')
        cache.delete_pattern(f'*recruit*{instance.pk}*')
    except Exception as e:
        # 캐시 삭제 실패는 로그만 남기고 진행
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[Cache Warning] JobNotice cache invalidation failed: {e}")


@receiver(post_delete, sender=JobNotice)
def invalidate_recruit_cache_on_delete(sender, instance, **kwargs):
    """
    JobNotice 삭제 시 캐시 무효화
    """
    try:
        cache.delete_pattern('*recruit*')
        cache.delete_pattern(f'*recruit*{instance.pk}*')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[Cache Warning] JobNotice cache invalidation on delete failed: {e}")


@receiver(post_save, sender=Company)
def invalidate_company_cache_on_save(sender, instance, created, **kwargs):
    """
    Company 정보 수정 시 해당 회사의 모든 공고 캐시 무효화
    """
    try:
        # 회사 관련 공고 캐시 패턴 전체 삭제
        cache.delete_pattern('*recruit*')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[Cache Warning] Company cache invalidation failed: {e}")
