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
    - 목록 캐시 삭제
    - 해당 상세 캐시 삭제
    """
    # 목록 API 캐시 무효화 (모든 페이지)
    # Note: 정확한 URL 패턴 캐시 삭제는 어려우므로,
    # 나중에 Redis의 키 패턴 매칭으로 개선 가능
    try:
        cache.delete('/api/v1/recruit/')
        cache.delete(f'/api/v1/recruit/{instance.pk}/')
    except Exception as e:
        # 캐시 삭제 실패는 로그만 남기고 진행
        print(f"[Cache Warning] JobNotice cache invalidation failed: {e}")


@receiver(post_delete, sender=JobNotice)
def invalidate_recruit_cache_on_delete(sender, instance, **kwargs):
    """
    JobNotice 삭제 시 캐시 무효화
    """
    try:
        cache.delete('/api/v1/recruit/')
        cache.delete(f'/api/v1/recruit/{instance.pk}/')
    except Exception as e:
        print(f"[Cache Warning] JobNotice cache invalidation on delete failed: {e}")


@receiver(post_save, sender=Company)
def invalidate_company_cache_on_save(sender, instance, created, **kwargs):
    """
    Company 정보 수정 시 해당 회사의 모든 공고 캐시 무효화
    """
    try:
        # 회사 소유 공고들의 캐시 무효화
        for job in JobNotice.objects.filter(company=instance):
            cache.delete(f'/api/v1/recruit/{job.pk}/')
    except Exception as e:
        print(f"[Cache Warning] Company cache invalidation failed: {e}")
