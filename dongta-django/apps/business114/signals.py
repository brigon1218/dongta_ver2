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
    - 목록 캐시 삭제
    - 해당 상세 캐시 삭제
    """
    try:
        cache.delete('/api/v1/business114/')
        cache.delete(f'/api/v1/business114/{instance.pk}/')
    except Exception as e:
        # 캐시 삭제 실패는 로그만 남기고 진행
        print(f"[Cache Warning] Business cache invalidation failed: {e}")


@receiver(post_delete, sender=Business)
def invalidate_business_cache_on_delete(sender, instance, **kwargs):
    """
    Business 삭제 시 캐시 무효화
    """
    try:
        cache.delete('/api/v1/business114/')
        cache.delete(f'/api/v1/business114/{instance.pk}/')
    except Exception as e:
        print(f"[Cache Warning] Business cache invalidation on delete failed: {e}")
