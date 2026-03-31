"""
business114 앱 Signal 핸들러
- Business 생성/수정/삭제 시 캐시 무효화
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Business


@receiver(post_save, sender=Business)
def invalidate_business_cache_on_save(sender, instance, created, **kwargs):
    """
    Business 생성/수정 시 캐시 무효화
    - delete_pattern()으로 URL 기반 캐시 패턴 전체 삭제
    """
    try:
        # @cache_page 는 해시된 키를 사용하므로 delete_pattern()으로 와일드카드 삭제
        cache.delete_pattern('*business*')
        cache.delete_pattern(f'*business*{instance.pk}*')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[Cache Warning] Business cache invalidation failed: {e}")


@receiver(post_delete, sender=Business)
def invalidate_business_cache_on_delete(sender, instance, **kwargs):
    """
    Business 삭제 시 캐시 무효화
    """
    try:
        cache.delete_pattern('*business*')
        cache.delete_pattern(f'*business*{instance.pk}*')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[Cache Warning] Business cache invalidation on delete failed: {e}")
