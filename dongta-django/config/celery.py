"""
config/celery.py

Celery 애플리케이션 설정.

큐 구성:
    sync     : MySQL → PostgreSQL 회원/업체 동기화 (2 replicas)
    payment  : 결제 동기화 (1 replica)
    default  : 기타 비동기 작업

Beat 스케줄:
    poll_pending_events     : 5분마다 PENDING 이벤트 일괄 발행
    verify_sync_integrity   : 매시간 정합성 검증
"""
import os

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

app = Celery('dongta')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ---------------------------------------------------------------------------
# 큐 및 Exchange 정의
# ---------------------------------------------------------------------------
default_exchange = Exchange('default', type='direct')
sync_exchange = Exchange('sync', type='direct')
payment_exchange = Exchange('payment', type='direct')

app.conf.task_queues = (
    Queue('default', default_exchange, routing_key='default'),
    Queue('sync', sync_exchange, routing_key='sync'),
    Queue('payment', payment_exchange, routing_key='payment'),
)
app.conf.task_default_queue = 'default'
app.conf.task_default_exchange = 'default'
app.conf.task_default_routing_key = 'default'

# ---------------------------------------------------------------------------
# 태스크 라우팅
# ---------------------------------------------------------------------------
app.conf.task_routes = {
    # sync 큐
    'apps.sync.tasks.process_event_outbox': {'queue': 'sync'},
    'apps.sync.tasks.poll_pending_events': {'queue': 'sync'},
    'apps.sync.tasks.verify_sync_integrity': {'queue': 'sync'},
    'apps.sync.tasks.clean_old_event_logs': {'queue': 'sync'},
    # payment 큐 (향후 결제 비동기 작업)
    'apps.payment.tasks.*': {'queue': 'payment'},
}

# ---------------------------------------------------------------------------
# Celery Beat 스케줄
# ---------------------------------------------------------------------------
app.conf.beat_schedule = {
    # 5분마다 PENDING EventOutbox 일괄 처리
    'poll-pending-events-every-5min': {
        'task': 'apps.sync.tasks.poll_pending_events',
        'schedule': 300,  # 300초 = 5분
        'options': {'queue': 'sync'},
    },
    # 매시간 정합성 검증 (분 0초)
    'verify-sync-integrity-hourly': {
        'task': 'apps.sync.tasks.verify_sync_integrity',
        'schedule': crontab(minute=0),
        'options': {'queue': 'sync'},
    },
    # 매일 02:00 — 7일 이상 처리된 이벤트 로그 / SyncLog 정리
    'clean-old-event-logs-daily': {
        'task': 'apps.sync.tasks.clean_old_event_logs',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'sync'},
    },
}

# ---------------------------------------------------------------------------
# 직렬화 / 결과 / 작업 설정
# ---------------------------------------------------------------------------
app.conf.update(
    # 직렬화
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    # 타임존
    timezone='Asia/Seoul',
    enable_utc=True,
    # 결과 만료 (1일)
    result_expires=86400,
    # Worker 안정성
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # 태스크 시간 제한
    task_soft_time_limit=300,   # 5분 soft limit
    task_time_limit=360,        # 6분 hard limit
)
