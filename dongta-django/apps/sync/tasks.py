"""
apps/sync/tasks.py

MySQL → PostgreSQL 동기화 Celery Tasks.

큐 구성:
- sync  : 회원/업체 데이터 동기화 (2 workers)
- payment: 결제 데이터 동기화 (1 worker)
- default: 기타 작업
"""
from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _get_outbox_model():
    """순환 참조 방지를 위해 런타임에 임포트"""
    from apps.sync.models import EventOutbox, EventStatus
    return EventOutbox, EventStatus


def _process_member_event(payload: dict[str, Any], event_type: str) -> None:
    """
    회원 이벤트 처리: MySQL TBL_MEMB → PostgreSQL accounts_member

    MySQL 컬럼 매핑:
        memb_idx        → id
        memb_id         → username
        memb_encrypt_passwd → password (md5$ 접두사 추가)
        memb_name       → name
        memb_email      → email
        memb_level      → level
        memb_hp1~3      → phone (정규화)
        memb_tel1~4     → landline
        memb_region     → region
        memb_corp       → corp_name
        memb_type       → member_type
        memb_class      → member_class
        memb_post1~2    → postal_code
        memb_addr1~2    → address
        memb_point      → point
        memb_mailflag   → email_opt_in
        memb_abroadflag → is_overseas
        memb_abroadapplyflag → overseas_approved
        memb_lastlogin  → last_login_at
        memb_logincount → login_count
        memb_wantquitflag → want_quit
        memb_quitreason → quit_reason
        memb_text       → memo
        memb_ip         → reg_ip
    """
    from apps.accounts.models import Member

    memb_idx: int = payload.get('memb_idx')
    if not memb_idx:
        raise ValueError('payload에 memb_idx가 없습니다.')

    # 전화번호 정규화: hp1+hp2+hp3 → 010-1234-5678
    phone_parts = [
        str(payload.get('memb_hp1', '')).strip(),
        str(payload.get('memb_hp2', '')).strip(),
        str(payload.get('memb_hp3', '')).strip(),
    ]
    phone = '-'.join(p for p in phone_parts if p) or payload.get('phone', '')

    landline_parts = [
        str(payload.get('memb_tel1', '')).strip(),
        str(payload.get('memb_tel2', '')).strip(),
        str(payload.get('memb_tel3', '')).strip(),
        str(payload.get('memb_tel4', '')).strip(),
    ]
    landline = '-'.join(p for p in landline_parts if p)

    postal_code = (
        str(payload.get('memb_post1', '')).strip() + str(payload.get('memb_post2', '')).strip()
    ).strip() or payload.get('postal_code', '')

    address = ' '.join(filter(None, [
        str(payload.get('memb_addr1', '')).strip(),
        str(payload.get('memb_addr2', '')).strip(),
    ])) or payload.get('address', '')

    # 패스워드: MD5 해시 앞에 md5$ 접두사 추가 (로그인 시 업그레이드용)
    raw_password = payload.get('memb_encrypt_passwd', '')
    legacy_password = f"md5${raw_password}" if raw_password else ""

    defaults = {
        'username': payload.get('memb_id', ''),
        'password': legacy_password,
        'name': payload.get('memb_name', ''),
        'email': payload.get('memb_email', ''),
        'level': int(payload.get('memb_level', 9)),
        'phone': phone,
        'landline': landline,
        'region': payload.get('memb_region', ''),
        'corp_name': payload.get('memb_corp', ''),
        'member_type': payload.get('memb_type', ''),
        'member_class': payload.get('memb_class', ''),
        'postal_code': postal_code,
        'address': address,
        'point': int(payload.get('memb_point', 0)),
        'email_opt_in': bool(int(payload.get('memb_mailflag', 1))),
        'is_overseas': bool(int(payload.get('memb_abroadflag', 0))),
        'overseas_approved': bool(int(payload.get('memb_abroadapplyflag', 0))),
        'login_count': int(payload.get('memb_logincount', 0)),
        'want_quit': bool(int(payload.get('memb_wantquitflag', 0))),
        'quit_reason': payload.get('memb_quitreason', ''),
        'memo': payload.get('memb_text', ''),
        'reg_ip': payload.get('memb_ip'),
    }

    # 날짜 필드 처리
    last_login = payload.get('memb_lastlogin')
    if last_login:
        try:
            defaults['last_login_at'] = timezone.make_aware(timezone.datetime.fromisoformat(str(last_login)))
        except (ValueError, TypeError):
            pass

    with transaction.atomic():
        member, created = Member.objects.update_or_create(
            id=memb_idx,
            defaults=defaults,
        )

    action = '생성' if created else '업데이트'
    logger.info('회원 %s 완료: id=%s username=%s', action, memb_idx, defaults['username'])


def _process_business_event(payload: dict[str, Any]) -> None:
    """
    업체 이벤트 처리: MySQL TBL_YELLOW → PostgreSQL business114_business
    """
    from apps.business114.models import Business

    yellow_idx: int = payload.get('yellow_idx')
    if not yellow_idx:
        raise ValueError('payload에 yellow_idx가 없습니다.')

    # 파이프(|) 구분 품목 → JSON 리스트
    items_raw = str(payload.get('yellow_item', '')).strip()
    items = [int(i) for i in items_raw.split('|') if i.isdigit()] if items_raw else []

    defaults = {
        'member_id': payload.get('memb_idx'),
        'business_type': int(payload.get('yellow_class', 1)),
        'corp_name': payload.get('yellow_corpname', ''),
        'phone': payload.get('yellow_tel', ''),
        'fax': payload.get('yellow_fax', ''),
        'homepage': payload.get('yellow_homepage', ''),
        'postal_code': payload.get('yellow_post', ''),
        'address': f"{payload.get('yellow_addr1', '')} {payload.get('yellow_addr2', '')}".strip(),
        'industry_type': int(payload.get('yellow_type', 0)),
        'items': items,
        'location_info': payload.get('yellow_locainfo', ''),
        'keywords': payload.get('yellow_keyword', ''),
        'description': payload.get('yellow_desc', ''),
        'logo_image': payload.get('yellow_img', ''),
        'view_count': int(payload.get('yellow_hit', 0)),
        'total_payment': int(payload.get('yellow_totpay', 0)),
        'payment_method': payload.get('yellow_pay_method', ''),
        'approval_no': payload.get('yellow_ack_no', ''),
        'is_approved': bool(int(payload.get('yellow_successflag', 0))),
    }

    with transaction.atomic():
        Business.objects.update_or_create(id=yellow_idx, defaults=defaults)

    logger.info('업체 동기화 완료: id=%s corp_name=%s', yellow_idx, defaults['corp_name'])


def _process_company_event(payload: dict[str, Any]) -> None:
    """
    채용 회사 이벤트 처리: MySQL TBL_JOBOFFER → PostgreSQL recruit_company
    """
    from apps.recruit.models import Company

    offer_idx: int = payload.get('offer_idx')
    if not offer_idx:
        raise ValueError('payload에 offer_idx가 없습니다.')

    defaults = {
        'member_id': payload.get('memb_idx'),
        'company_name': payload.get('offer_name', ''),
        'phone': payload.get('offer_tel', ''),
        'email': payload.get('offer_email', ''),
        'homepage': payload.get('offer_homepage', ''),
        'postal_code': payload.get('offer_post', ''),
        'address': payload.get('offer_addr', ''),
        'introduction': payload.get('offer_introduce', ''),
        'has_notice': bool(int(payload.get('offer_noticeflag', 0))),
    }

    with transaction.atomic():
        Company.objects.update_or_create(id=offer_idx, defaults=defaults)

    logger.info('채용회사 동기화 완료: id=%s company_name=%s', offer_idx, defaults['company_name'])


def _process_recruit_event(payload: dict[str, Any]) -> None:
    """
    채용 공고 이벤트 처리: MySQL TBL_JOBNOTICE → PostgreSQL recruit_job_notice
    """
    from apps.recruit.models import JobNotice

    notice_idx: int = payload.get('notice_idx')
    if not notice_idx:
        raise ValueError('payload에 notice_idx가 없습니다.')

    # 파이프(|) 구분 직종 → JSON 리스트
    occ_raw = str(payload.get('notice_occupation', '')).strip()
    occupations = [o for o in occ_raw.split('|') if o] if occ_raw else []

    defaults = {
        'member_id': payload.get('memb_idx'),
        'company_id': payload.get('offer_idx'),
        'employment_type': payload.get('notice_kind', ''),
        'title': payload.get('notice_title', ''),
        'occupations': occupations,
        'career_required': bool(int(payload.get('notice_career', 0))),
        'is_approved': bool(int(payload.get('notice_successflag', 0))),
        'approval_no': payload.get('notice_ack_no', ''),
        'payment_code': payload.get('notice_pay_code', ''),
        'is_premium': bool(int(payload.get('notice_premium', 0))),
    }

    # 날짜 필드 처리
    for date_field in ['notice_startdate', 'notice_enddate']:
        val = payload.get(date_field)
        if val:
            target_key = 'premium_start_date' if 'start' in date_field else 'premium_end_date'
            defaults[target_key] = val

    with transaction.atomic():
        JobNotice.objects.update_or_create(id=notice_idx, defaults=defaults)

    logger.info('채용공고 동기화 완료: id=%s title=%s', notice_idx, defaults['title'])


def _process_job_seeker_event(payload: dict[str, Any]) -> None:
    """
    구직자/이력서 이벤트 처리: MySQL TBL_JOBHUNTER → PostgreSQL recruit_job_seeker
    """
    from apps.recruit.models import JobSeeker

    hunter_idx: int = payload.get('hunter_idx')
    if not hunter_idx:
        raise ValueError('payload에 hunter_idx가 없습니다.')

    defaults = {
        'member_id': payload.get('memb_idx'),
        'name': payload.get('hunter_name', ''),
        'birth_date': payload.get('hunter_birth') or None,
        'gender': payload.get('hunter_gender', ''),
        'phone': payload.get('hunter_tel', ''),
        'email': payload.get('hunter_email', ''),
        'address': payload.get('hunter_addr', ''),
        'profile_image': payload.get('hunter_img', ''),
        'resume_registered': bool(int(payload.get('hunter_resume_flag', 0))),
    }

    with transaction.atomic():
        JobSeeker.objects.update_or_create(id=hunter_idx, defaults=defaults)

    logger.info('구직자 동기화 완료: id=%s name=%s', hunter_idx, defaults['name'])


def _process_payment_event(payload: dict[str, Any]) -> None:
    """
    결제 이벤트 처리: MySQL DongtaPointCharge → PostgreSQL payment_history

    MySQL 컬럼 매핑:
        nChargeIdx      → id (참조용)
        nMembIdx        → member_id
        nChargePrice    → amount
        nChargeDP       → point_amount
        sPayMethod      → pay_method
        bSuccess        → is_success
        sResultCode     → result_code
        sResultMsg      → result_message
        sOrderId        → danal_order_id
    """
    from apps.payment.models import PaymentHistory, PointAccount

    member_id: int = payload.get('nMembIdx')
    if not member_id:
        raise ValueError('payload에 nMembIdx가 없습니다.')

    order_id: str = payload.get('sOrderId', '')
    is_success: bool = bool(int(payload.get('bSuccess', 0)))
    amount: int = int(payload.get('nChargePrice', 0))
    point_amount: int = int(payload.get('nChargeDP', 0))

    with transaction.atomic():
        payment, created = PaymentHistory.objects.update_or_create(
            danal_order_id=order_id if order_id else None,
            defaults={
                'member_id': member_id,
                'amount': amount,
                'point_amount': point_amount,
                'pay_method': payload.get('sPayMethod', 'card'),
                'is_success': is_success,
                'result_code': payload.get('sResultCode', ''),
                'result_message': payload.get('sResultMsg', ''),
                'confirmed_at': timezone.now() if is_success else None,
            },
        )

        if is_success and created:
            point_account, _ = PointAccount.objects.select_for_update().get_or_create(
                member_id=member_id
            )
            point_account.total_charged += point_amount
            point_account.last_charged_at = timezone.now()
            point_account.save(update_fields=['total_charged', 'last_charged_at'])
            logger.info('포인트 충전 동기화: member_id=%s +%d DP', member_id, point_amount)

    logger.info('결제 동기화 완료: order_id=%s is_success=%s', order_id, is_success)


# ---------------------------------------------------------------------------
# Celery Tasks
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    queue='sync',
    max_retries=3,
    default_retry_delay=60,  # 60초 후 재시도
    name='apps.sync.tasks.process_event_outbox',
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_event_outbox(self, outbox_id: int) -> dict[str, Any]:
    """
    단일 EventOutbox 항목을 처리한다.

    Args:
        outbox_id: EventOutbox.pk

    Returns:
        처리 결과 딕셔너리
    """
    EventOutbox, EventStatus = _get_outbox_model()

    try:
        outbox = EventOutbox.objects.get(pk=outbox_id)
    except EventOutbox.DoesNotExist:
        logger.error('EventOutbox not found: id=%s', outbox_id)
        return {'status': 'not_found', 'outbox_id': outbox_id}

    if outbox.status not in (EventStatus.PENDING, EventStatus.FAILED):
        logger.debug('EventOutbox skip (status=%s): id=%s', outbox.status, outbox_id)
        return {'status': 'skipped', 'outbox_id': outbox_id}

    outbox.mark_processing()

    try:
        event_type = outbox.event_type
        payload = outbox.payload

        if event_type in (
            'member.insert',
            'member.update',
        ):
            _process_member_event(payload, event_type)
        elif event_type == 'payment.insert':
            _process_payment_event(payload)
        elif event_type in ('business.insert', 'business.update'):
            _process_business_event(payload)
        elif event_type in ('company.insert', 'company.update'):
            _process_company_event(payload)
        elif event_type in ('recruit.insert', 'recruit.update'):
            _process_recruit_event(payload)
        elif event_type in ('job_seeker.insert', 'job_seeker.update'):
            _process_job_seeker_event(payload)
        else:
            raise ValueError(f'알 수 없는 event_type: {event_type}')

        outbox.mark_done()
        return {'status': 'done', 'outbox_id': outbox_id, 'event_type': event_type}

    except Exception as exc:
        error_msg = str(exc)
        outbox.mark_failed(error_msg)
        logger.exception('EventOutbox 처리 실패: id=%s', outbox_id)

        # Celery 자동 재시도 (outbox 재시도와 별개)
        if outbox.retry_count < outbox.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

        return {'status': 'failed', 'outbox_id': outbox_id, 'error': error_msg}


@shared_task(
    queue='sync',
    name='apps.sync.tasks.poll_pending_events',
    acks_late=True,
)
def poll_pending_events() -> dict[str, Any]:
    """
    PENDING 상태 EventOutbox를 일괄 조회해 process_event_outbox 태스크를 발행한다.
    Celery Beat 스케줄러에 의해 5분 주기로 실행된다.
    """
    from apps.sync.models import EventOutbox, EventStatus

    pending_ids = list(
        EventOutbox.objects.filter(
            status__in=[EventStatus.PENDING, EventStatus.FAILED],
        ).exclude(
            status=EventStatus.DEAD_LETTER,
        ).values_list('id', flat=True)[:500]  # 배치 크기 제한
    )

    dispatched = 0
    for outbox_id in pending_ids:
        process_event_outbox.apply_async(args=[outbox_id], queue='sync')
        dispatched += 1

    logger.info('poll_pending_events: %d개 태스크 발행', dispatched)
    return {'dispatched': dispatched, 'outbox_ids': pending_ids}


@shared_task(
    queue='sync',
    name='apps.sync.tasks.verify_sync_integrity',
    acks_late=True,
)
def verify_sync_integrity() -> dict[str, Any]:
    """
    MySQL과 PostgreSQL 간 데이터 정합성 검증.
    Celery Beat에 의해 매시간 실행된다.

    - DEAD_LETTER 항목 알림
    - 장기 미처리 PENDING 항목 감지
    """
    from apps.sync.models import EventOutbox, EventStatus, SyncLog

    now = timezone.now()
    one_hour_ago = now - timezone.timedelta(hours=1)

    dead_letter_count = EventOutbox.objects.filter(
        status=EventStatus.DEAD_LETTER
    ).count()

    stale_pending_count = EventOutbox.objects.filter(
        status=EventStatus.PENDING,
        created_at__lt=one_hour_ago,
    ).count()

    result = 'success'
    detail_parts = []

    if dead_letter_count > 0:
        result = 'partial'
        detail_parts.append(f'DLQ 항목 {dead_letter_count}건 존재 — 수동 확인 필요')
        logger.warning('verify_sync_integrity: DLQ %d건', dead_letter_count)

    if stale_pending_count > 0:
        result = 'partial'
        detail_parts.append(f'1시간 이상 PENDING {stale_pending_count}건 — Worker 상태 확인 필요')
        logger.warning('verify_sync_integrity: stale PENDING %d건', stale_pending_count)

    if not detail_parts:
        detail_parts.append('정상')

    SyncLog.objects.create(
        task_id=verify_sync_integrity.request.id or 'beat-scheduled',
        finished_at=now,
        result=result,
        processed_count=0,
        failed_count=dead_letter_count,
        detail='\n'.join(detail_parts),
    )

    logger.info('verify_sync_integrity 완료: result=%s', result)
    return {
        'result': result,
        'dead_letter_count': dead_letter_count,
        'stale_pending_count': stale_pending_count,
    }


@shared_task(
    queue='sync',
    name='apps.sync.tasks.process_php_events',
    acks_late=True,
)
def process_php_events() -> dict[str, Any]:
    """
    MySQL TBL_EVENT_OUTBOX에서 PHP 시스템이 생성한 이벤트를 폴링하여 처리한다.
    (PHP → Django 방향 동기화)

    MySQL에는 triggers와 프로시저에 의해 이벤트가 삽입되고,
    이 태스크가 이들을 주기적으로 확인한다.

    Returns:
        처리 결과: {'processed': N, 'failed': M}
    """
    from django.db import connections

    processed = 0
    failed = 0

    try:
        with connections['legacy'].cursor() as cursor:
            # MySQL의 TBL_EVENT_OUTBOX에서 미처리 이벤트 조회
            # (상세 쿼리는 MySQL DDL에서 정의)
            cursor.execute("""
                SELECT
                    event_id,
                    event_type,
                    aggregate_type,
                    aggregate_id,
                    payload_json,
                    created_at
                FROM TBL_EVENT_OUTBOX
                WHERE status = 'PENDING'
                  AND created_at > NOW() - INTERVAL 24 HOUR
                ORDER BY created_at ASC
                LIMIT 100
            """)

            rows = cursor.fetchall()

            for row in rows:
                event_id, event_type, agg_type, agg_id, payload_str, created_at = row
                try:
                    import json
                    payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str

                    # PostgreSQL EventOutbox 매핑
                    # MySQL TBL_EVENT_OUTBOX → PostgreSQL sync_event_outbox
                    outbox = _create_outbox_from_mysql(
                        event_type=event_type,
                        aggregate_type=agg_type,
                        aggregate_id=agg_id,
                        payload=payload,
                        mysql_event_id=event_id,
                    )

                    # EventOutbox processing task 발행
                    if outbox:
                        process_event_outbox.apply_async(args=[outbox.id], queue='sync')
                        processed += 1

                        # MySQL에서 이벤트 상태 업데이트 (선택사항)
                        cursor.execute(
                            "UPDATE TBL_EVENT_OUTBOX SET status = %s WHERE event_id = %s",
                            ['PROCESSED', event_id]
                        )

                except Exception as e:
                    failed += 1
                    logger.exception('process_php_events: event_id=%s error=%s', event_id, str(e))

        logger.info('process_php_events: processed=%d failed=%d', processed, failed)
        return {'processed': processed, 'failed': failed}

    except Exception as e:
        logger.exception('process_php_events 작업 실패: %s', str(e))
        return {'processed': 0, 'failed': -1, 'error': str(e)}


def _create_outbox_from_mysql(
    event_type: str,
    aggregate_type: str,
    aggregate_id: int,
    payload: dict[str, Any],
    mysql_event_id: int,
) -> Any:
    """
    MySQL TBL_EVENT_OUTBOX의 이벤트를 PostgreSQL EventOutbox로 매핑한다.

    Args:
        event_type: 'member.insert', 'member.update', etc.
        aggregate_type: 'member', 'recruit', 'payment', etc.
        aggregate_id: 원본 레코드 ID
        payload: 이벤트 페이로드 (JSON)
        mysql_event_id: MySQL의 event_id (추적용)

    Returns:
        생성된 EventOutbox 인스턴스 또는 None (중복이면 None)
    """
    from apps.sync.models import EventOutbox, EventSource

    # 중복 체크: correlation_id로 mysql_event_id를 사용하여 중복 방지
    existing = EventOutbox.objects.filter(
        correlation_id=f'mysql:{mysql_event_id}',
        aggregate_id=aggregate_id,
    ).exists()

    if existing:
        logger.debug('Duplicate event skipped: mysql_event_id=%s', mysql_event_id)
        return None

    try:
        outbox = EventOutbox.objects.create(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            source=EventSource.MYSQL,
            correlation_id=f'mysql:{mysql_event_id}',
        )
        logger.info(
            'EventOutbox created from MySQL: id=%s type=%s',
            outbox.id,
            event_type,
        )
        return outbox
    except Exception as e:
        logger.exception('_create_outbox_from_mysql failed: %s', str(e))
        return None


@shared_task(
    queue='sync',
    name='apps.sync.tasks.clean_old_event_logs',
    acks_late=True,
)
def clean_old_event_logs() -> dict[str, int]:
    """
    7일 이상 처리된 이벤트 로그 및 동기화 이력을 삭제한다.
    Celery Beat에 의해 매일 오전 2시에 실행된다.

    대상:
    - EventOutbox: status=DONE 이고 processed_at < 7일 전
    - SyncLog: started_at < 7일 전

    Returns:
        {'deleted_outbox': N, 'deleted_synclog': M}
    """
    from datetime import timedelta

    from apps.sync.models import EventOutbox, EventStatus, SyncLog

    cutoff_date = timezone.now() - timedelta(days=7)

    # 처리 완료(DONE) 상태이면서 7일 이상 경과한 EventOutbox 삭제
    deleted_outbox, _ = EventOutbox.objects.filter(
        status=EventStatus.DONE,
        processed_at__lt=cutoff_date,
    ).delete()

    # 7일 이상 경과한 SyncLog 삭제
    deleted_synclog, _ = SyncLog.objects.filter(
        started_at__lt=cutoff_date,
    ).delete()

    logger.info(
        '[CLEANUP] EventOutbox %d건, SyncLog %d건 삭제 (기준일: %s)',
        deleted_outbox,
        deleted_synclog,
        cutoff_date.strftime('%Y-%m-%d %H:%M'),
    )
    return {'deleted_outbox': deleted_outbox, 'deleted_synclog': deleted_synclog}
