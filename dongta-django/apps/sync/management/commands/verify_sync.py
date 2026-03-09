"""
apps/sync/management/commands/verify_sync.py

MySQL ↔ PostgreSQL 동기화 상태 검증 커맨드.

사용법:
    python manage.py verify_sync
    python manage.py verify_sync --fix-stale
    python manage.py verify_sync --report-only
"""
import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'MySQL → PostgreSQL 동기화 상태를 검증하고 보고서를 출력합니다.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--fix-stale',
            action='store_true',
            default=False,
            help='1시간 이상 PENDING 상태인 이벤트를 재발행합니다.',
        )
        parser.add_argument(
            '--report-only',
            action='store_true',
            default=False,
            help='현황만 출력하고 수정하지 않습니다.',
        )
        parser.add_argument(
            '--stale-hours',
            type=int,
            default=1,
            help='장기 미처리로 간주할 시간 (기본: 1시간)',
        )

    def handle(self, *args, **options) -> None:
        from apps.sync.models import EventOutbox, EventStatus, SyncLog

        self.stdout.write(self.style.MIGRATE_HEADING('=== 동기화 상태 검증 시작 ==='))

        now = timezone.now()
        stale_threshold = now - timezone.timedelta(hours=options['stale_hours'])

        # 상태별 집계
        from django.db.models import Count
        counts = {
            row['status']: row['cnt']
            for row in EventOutbox.objects.values('status').annotate(cnt=Count('id'))
        }

        self.stdout.write('\n[상태별 EventOutbox 현황]')
        for status_value, label in EventStatus.choices:
            cnt = counts.get(status_value, 0)
            style = self.style.SUCCESS if cnt == 0 or status_value == 'done' else self.style.WARNING
            if status_value in ('dead_letter', 'failed') and cnt > 0:
                style = self.style.ERROR
            self.stdout.write(f'  {label:12}: {style(str(cnt))}')

        # 장기 PENDING 감지
        stale_pending = EventOutbox.objects.filter(
            status=EventStatus.PENDING,
            created_at__lt=stale_threshold,
        )
        stale_count = stale_pending.count()

        if stale_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[경고] {options["stale_hours"]}시간 이상 PENDING 이벤트: {stale_count}건'
                )
            )

            if options['fix_stale'] and not options['report_only']:
                self.stdout.write('  → 재발행 처리 중...')
                from apps.sync.tasks import process_event_outbox
                dispatched = 0
                for outbox in stale_pending.iterator():
                    process_event_outbox.apply_async(args=[outbox.pk], queue='sync')
                    dispatched += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  → {dispatched}건 재발행 완료')
                )

        # DLQ 확인
        dlq_count = counts.get(EventStatus.DEAD_LETTER, 0)
        if dlq_count > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'\n[오류] DLQ(최종실패) 이벤트: {dlq_count}건 — 수동 확인 필요'
                )
            )
            dlq_samples = EventOutbox.objects.filter(
                status=EventStatus.DEAD_LETTER
            ).order_by('-created_at')[:5]
            for item in dlq_samples:
                self.stdout.write(
                    f'  id={item.pk} type={item.event_type} '
                    f'aggregate_id={item.aggregate_id} '
                    f'error={item.error_message[:80]}'
                )

        # 최근 SyncLog
        last_log = SyncLog.objects.order_by('-started_at').first()
        if last_log:
            self.stdout.write(f'\n[마지막 동기화 실행]')
            self.stdout.write(f'  시작: {last_log.started_at}')
            self.stdout.write(f'  결과: {last_log.get_result_display()}')
            self.stdout.write(f'  처리: {last_log.processed_count}건 / 실패: {last_log.failed_count}건')
        else:
            self.stdout.write(self.style.WARNING('\n[경고] 동기화 실행 이력이 없습니다.'))

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 검증 완료 ==='))
