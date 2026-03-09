"""
apps/sync/models.py

MySQL → PostgreSQL 동기화를 위한 Event Outbox 패턴 모델.
MySQL 트리거가 TBL_EVENT_OUTBOX에 이벤트를 삽입하면
Celery Worker가 이를 읽어 PostgreSQL에 반영한다.

동기화 방향: MySQL(레거시, Master) → PostgreSQL(Django)
"""
from __future__ import annotations

import logging
from typing import Optional

from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class EventStatus(models.TextChoices):
    PENDING = 'pending', '대기'
    PROCESSING = 'processing', '처리중'
    DONE = 'done', '완료'
    FAILED = 'failed', '실패'
    DEAD_LETTER = 'dead_letter', '최종실패(DLQ)'


class EventType(models.TextChoices):
    MEMBER_INSERT = 'member.insert', '회원 신규'
    MEMBER_UPDATE = 'member.update', '회원 수정'
    PAYMENT_INSERT = 'payment.insert', '결제 신규'
    BUSINESS_INSERT = 'business.insert', '업체 신규'
    BUSINESS_UPDATE = 'business.update', '업체 수정'
    COMPANY_INSERT = 'company.insert', '채용회사 신규'
    COMPANY_UPDATE = 'company.update', '채용회사 수정'
    RECRUIT_INSERT = 'recruit.insert', '채용공고 신규'
    RECRUIT_UPDATE = 'recruit.update', '채용공고 수정'
    JOB_SEEKER_INSERT = 'job_seeker.insert', '구직자 신규'
    JOB_SEEKER_UPDATE = 'job_seeker.update', '구직자 수정'


class EventOutbox(models.Model):
    """
    MySQL Event Outbox (MySQL: TBL_EVENT_OUTBOX)

    MySQL 트리거 → TBL_EVENT_OUTBOX 삽입 → Celery polling → PostgreSQL 반영
    """
    id = models.BigAutoField(primary_key=True, verbose_name='PK')
    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,
        verbose_name='이벤트 유형',
        db_index=True,
    )
    aggregate_type = models.CharField(
        max_length=50,
        verbose_name='집계 유형',
        help_text='예: member, payment',
    )
    aggregate_id = models.BigIntegerField(
        verbose_name='원본 레코드 PK (MySQL)',
        db_index=True,
    )
    payload = models.JSONField(
        verbose_name='이벤트 페이로드',
        help_text='MySQL 원본 데이터 (JSON)',
    )
    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        default=EventStatus.PENDING,
        verbose_name='처리 상태',
        db_index=True,
    )
    retry_count = models.SmallIntegerField(
        default=0,
        verbose_name='재시도 횟수',
    )
    max_retries = models.SmallIntegerField(
        default=3,
        verbose_name='최대 재시도 횟수',
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='오류 메시지',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='생성일시',
        db_index=True,
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='처리완료일시',
    )

    class Meta:
        db_table = 'sync_event_outbox'
        verbose_name = '이벤트 아웃박스'
        verbose_name_plural = '이벤트 아웃박스 목록'
        ordering = ['created_at']
        indexes = [
            models.Index(
                fields=['status', 'created_at'],
                name='idx_outbox_status_created',
            ),
            models.Index(
                fields=['event_type', 'aggregate_id'],
                name='idx_outbox_type_aggregate',
            ),
        ]

    def __str__(self) -> str:
        return f'[{self.event_type}] aggregate_id={self.aggregate_id} status={self.status}'

    def mark_processing(self) -> None:
        """처리 시작 상태로 변경"""
        self.status = EventStatus.PROCESSING
        self.save(update_fields=['status'])

    def mark_done(self) -> None:
        """처리 완료 상태로 변경"""
        self.status = EventStatus.DONE
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_at'])

    def mark_failed(self, error: str) -> None:
        """실패 처리 — 재시도 횟수 초과 시 DLQ로 이동"""
        self.retry_count += 1
        self.error_message = error[:2000]  # 필드 길이 제한 방어

        if self.retry_count >= self.max_retries:
            self.status = EventStatus.DEAD_LETTER
            logger.error(
                'EventOutbox DLQ: id=%s type=%s aggregate_id=%s error=%s',
                self.pk, self.event_type, self.aggregate_id, error,
            )
        else:
            self.status = EventStatus.FAILED
            logger.warning(
                'EventOutbox retry %d/%d: id=%s type=%s',
                self.retry_count, self.max_retries, self.pk, self.event_type,
            )

        self.save(update_fields=['status', 'retry_count', 'error_message'])

    @property
    def can_retry(self) -> bool:
        return self.status == EventStatus.FAILED and self.retry_count < self.max_retries


class SyncLog(models.Model):
    """
    동기화 작업 실행 이력 — 운영 모니터링용
    """
    class SyncResult(models.TextChoices):
        SUCCESS = 'success', '성공'
        PARTIAL = 'partial', '부분성공'
        FAILURE = 'failure', '실패'

    task_id = models.CharField(
        max_length=100,
        verbose_name='Celery Task ID',
        db_index=True,
    )
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='시작일시')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='완료일시')
    result = models.CharField(
        max_length=20,
        choices=SyncResult.choices,
        verbose_name='결과',
    )
    processed_count = models.IntegerField(default=0, verbose_name='처리건수')
    failed_count = models.IntegerField(default=0, verbose_name='실패건수')
    detail = models.TextField(blank=True, verbose_name='상세 로그')

    class Meta:
        db_table = 'sync_log'
        verbose_name = '동기화 이력'
        verbose_name_plural = '동기화 이력 목록'
        ordering = ['-started_at']

    def __str__(self) -> str:
        return f'SyncLog {self.task_id} [{self.result}] {self.started_at}'
