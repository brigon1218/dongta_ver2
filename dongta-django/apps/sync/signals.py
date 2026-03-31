"""
Phase 2.1: Event Logging - Django Signal Handlers

Member와 JobNotice의 변경을 감지하여 EventOutbox에 이벤트를 기록한다.
이를 통해 MySQL → PostgreSQL 양방향 동기화를 지원한다.

Signal Flow:
1. accounts.Member.post_save  → create_member_event()
2. accounts.Member.post_delete → handle_member_delete()
3. recruit.JobNotice.post_save → create_recruit_event()
4. recruit.JobNotice.post_delete → handle_recruit_delete()
5. EventOutbox에 PENDING 상태로 저장
6. Celery task가 PENDING 이벤트를 폴링하여 처리

Note: post_delete 핸들러는 하드 삭제(DB에서 완전 제거) 시에만 발동한다.
소프트 삭제(is_deleted=True)는 post_save에서 감지한다.
"""

import logging
from typing import Any

from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


def _is_event_log_enabled() -> bool:
    """EVENT_LOG_ENABLED 설정값 확인"""
    return getattr(settings, 'EVENT_LOG_ENABLED', True)


def _get_correlation_id() -> str:
    """
    현재 요청의 correlation_id를 조회한다.
    RequestIDMiddleware에서 request.correlation_id로 설정됨.

    Threading context에서 correlation_id가 없으면 '-'를 반환한다.
    """
    import threading

    # 요청 컨텍스트에서 correlation_id 조회
    try:
        context = threading.current_thread().__dict__
        return context.get('correlation_id', '')
    except (AttributeError, RuntimeError):
        return ''


@receiver(post_save, sender='accounts.Member')
def create_member_event(sender: Any, instance: Any, created: bool, **kwargs) -> None:  # noqa: C901
    """
    Member 생성/수정 시 EventOutbox에 이벤트를 기록한다.

    Args:
        sender: Member model
        instance: 저장된 Member 인스턴스
        created: 신규 생성 여부
        **kwargs: 추가 인자
    """
    from apps.sync.models import EventOutbox, EventType, EventSource

    if not _is_event_log_enabled():
        return

    if instance.is_deleted:
        # 삭제된 회원은 이벤트 무시
        return

    event_type = EventType.MEMBER_INSERT if created else EventType.MEMBER_UPDATE

    payload = {
        'memb_idx': instance.id,
        'memb_id': instance.username,
        'memb_name': instance.name,
        'memb_email': instance.email,
        'memb_level': instance.level,
        'memb_hp1': instance.phone.split('-')[0] if instance.phone else '',
        'memb_hp2': instance.phone.split('-')[1] if instance.phone and len(instance.phone.split('-')) > 1 else '',
        'memb_hp3': instance.phone.split('-')[2] if instance.phone and len(instance.phone.split('-')) > 2 else '',
        'memb_region': instance.region,
        'memb_corp': instance.corp_name,
        'memb_type': instance.member_type,
        'memb_class': instance.member_class,
        'memb_post1': instance.postal_code,
        'memb_addr1': instance.address,
        'memb_point': instance.point,
        'memb_mailflag': 1 if instance.email_opt_in else 0,
        'memb_abroadflag': 1 if instance.is_overseas else 0,
        'memb_abroadapplyflag': 1 if instance.overseas_approved else 0,
        'memb_lastlogin': instance.last_login_at.isoformat() if instance.last_login_at else None,
        'memb_logincount': instance.login_count,
        'memb_wantquitflag': 1 if instance.want_quit else 0,
        'memb_quitreason': instance.quit_reason,
        'memb_text': instance.memo,
        'memb_ip': instance.reg_ip,
    }

    correlation_id = _get_correlation_id()

    try:
        EventOutbox.objects.create(
            event_type=event_type,
            aggregate_type='member',
            aggregate_id=instance.id,
            payload=payload,
            source=EventSource.DJANGO,
            correlation_id=correlation_id,
        )
        logger.info(
            'Member event created: type=%s id=%s correlation_id=%s',
            event_type,
            instance.id,
            correlation_id,
        )
    except Exception as e:
        logger.exception(
            'Failed to create Member event: id=%s error=%s',
            instance.id,
            str(e),
        )


@receiver(post_save, sender='recruit.JobNotice')
def create_recruit_event(sender: Any, instance: Any, created: bool, **kwargs) -> None:
    """
    JobNotice 생성/수정 시 EventOutbox에 이벤트를 기록한다.

    Args:
        sender: JobNotice model
        instance: 저장된 JobNotice 인스턴스
        created: 신규 생성 여부
        **kwargs: 추가 인자
    """
    from apps.sync.models import EventOutbox, EventType, EventSource

    if instance.is_deleted:
        # 삭제된 공고는 이벤트 무시
        return

    event_type = EventType.RECRUIT_INSERT if created else EventType.RECRUIT_UPDATE

    # occupations는 JSON 리스트이므로 파이프(|) 구분으로 변환
    occupations = '|'.join(instance.occupations) if instance.occupations else ''

    payload = {
        'notice_idx': instance.id,
        'memb_idx': instance.member_id,
        'offer_idx': instance.company_id,
        'notice_kind': instance.employment_type,
        'notice_title': instance.title,
        'notice_occupation': occupations,
        'notice_career': 1 if instance.career_required else 0,
        'notice_successflag': 1 if instance.is_approved else 0,
        'notice_ack_no': instance.approval_no,
        'notice_pay_code': instance.payment_code,
        'notice_premium': 1 if instance.is_premium else 0,
        'notice_startdate': instance.premium_start_date.isoformat() if instance.premium_start_date else None,
        'notice_enddate': instance.premium_end_date.isoformat() if instance.premium_end_date else None,
    }

    correlation_id = _get_correlation_id()

    try:
        EventOutbox.objects.create(
            event_type=event_type,
            aggregate_type='recruit',
            aggregate_id=instance.id,
            payload=payload,
            source=EventSource.DJANGO,
            correlation_id=correlation_id,
        )
        logger.info(
            'Recruit event created: type=%s id=%s correlation_id=%s',
            event_type,
            instance.id,
            correlation_id,
        )
    except Exception as e:
        logger.exception(
            'Failed to create Recruit event: id=%s error=%s',
            instance.id,
            str(e),
        )


# =============================================================================
# post_delete 핸들러 (Design S6.1 — 하드 삭제 이벤트 추적)
# =============================================================================

@receiver(post_delete, sender='accounts.Member')
def handle_member_delete(sender: Any, instance: Any, **kwargs) -> None:
    """
    Member 하드 삭제 시 EventOutbox에 삭제 이벤트를 기록한다.

    Note: 소프트 삭제(is_deleted=True)는 post_save에서 감지하며,
    이 핸들러는 DB에서 완전 제거되는 경우에만 동작한다.
    """
    from apps.sync.models import EventOutbox, EventSource

    if not _is_event_log_enabled():
        return

    correlation_id = _get_correlation_id()

    # 삭제된 인스턴스의 핵심 식별 정보만 페이로드로 기록
    payload = {
        'memb_idx': instance.id,
        'memb_id': instance.username,
        'memb_name': instance.name,
        'memb_email': instance.email,
        'deleted_at': timezone.now().isoformat(),
    }

    try:
        EventOutbox.objects.create(
            event_type='member.delete',
            aggregate_type='member',
            aggregate_id=instance.id,
            payload=payload,
            source=EventSource.DJANGO,
            correlation_id=correlation_id,
        )
        logger.info(
            'Member delete event created: id=%s correlation_id=%s',
            instance.id,
            correlation_id,
        )
    except Exception as e:
        logger.exception(
            'Failed to create Member delete event: id=%s error=%s',
            instance.id,
            str(e),
        )


@receiver(post_delete, sender='recruit.JobNotice')
def handle_recruit_delete(sender: Any, instance: Any, **kwargs) -> None:
    """
    JobNotice 하드 삭제 시 EventOutbox에 삭제 이벤트를 기록한다.

    Note: 소프트 삭제는 post_save에서 감지하며,
    이 핸들러는 DB에서 완전 제거되는 경우에만 동작한다.
    """
    from apps.sync.models import EventOutbox, EventSource

    if not _is_event_log_enabled():
        return

    correlation_id = _get_correlation_id()

    payload = {
        'notice_idx': instance.id,
        'memb_idx': instance.member_id,
        'offer_idx': instance.company_id,
        'notice_title': instance.title,
        'deleted_at': timezone.now().isoformat(),
    }

    try:
        EventOutbox.objects.create(
            event_type='recruit.delete',
            aggregate_type='recruit',
            aggregate_id=instance.id,
            payload=payload,
            source=EventSource.DJANGO,
            correlation_id=correlation_id,
        )
        logger.info(
            'Recruit delete event created: id=%s correlation_id=%s',
            instance.id,
            correlation_id,
        )
    except Exception as e:
        logger.exception(
            'Failed to create Recruit delete event: id=%s error=%s',
            instance.id,
            str(e),
        )
