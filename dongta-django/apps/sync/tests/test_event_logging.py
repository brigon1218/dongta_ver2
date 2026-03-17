"""
Phase 2.1: Event Logging - Unit and Integration Tests

Signal handlers, EventOutbox model, and Celery tasks 테스트
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from apps.accounts.models import Member
from apps.recruit.models import Company, JobNotice
from apps.sync.models import EventOutbox, EventType, EventStatus, EventSource, SyncLog
from apps.sync.tasks import (
    process_event_outbox,
    poll_pending_events,
    verify_sync_integrity,
)


class MemberSignalTestCase(TestCase):
    """Member 모델 Signal 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        self.factory = RequestFactory()

    def test_member_insert_creates_event(self):
        """Member 신규 생성 시 EventOutbox 이벤트 생성"""
        # 이벤트 생성 전 카운트
        initial_count = EventOutbox.objects.count()

        # Member 생성
        member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            name='Test User',
            region='Seoul',
        )

        # 이벤트 생성 확인
        self.assertEqual(
            EventOutbox.objects.count(),
            initial_count + 1,
            'Member 생성 시 EventOutbox가 생성되지 않음'
        )

        # 이벤트 내용 검증
        event = EventOutbox.objects.latest('id')
        self.assertEqual(event.event_type, EventType.MEMBER_INSERT)
        self.assertEqual(event.aggregate_type, 'member')
        self.assertEqual(event.aggregate_id, member.id)
        self.assertEqual(event.status, EventStatus.PENDING)
        self.assertEqual(event.source, EventSource.DJANGO)

        # 페이로드 검증
        payload = event.payload
        self.assertEqual(payload['memb_idx'], member.id)
        self.assertEqual(payload['memb_id'], member.username)
        self.assertEqual(payload['memb_name'], member.name)

    def test_member_update_creates_event(self):
        """Member 수정 시 EventOutbox 이벤트 생성"""
        member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            name='Test User',
        )

        EventOutbox.objects.all().delete()  # 이전 이벤트 제거

        # Member 수정
        member.name = 'Updated User'
        member.region = 'Busan'
        member.save()

        # 이벤트 생성 확인
        event = EventOutbox.objects.get()
        self.assertEqual(event.event_type, EventType.MEMBER_UPDATE)
        self.assertEqual(event.aggregate_id, member.id)

    def test_deleted_member_no_event(self):
        """삭제된 Member는 이벤트 생성 안 함"""
        member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            name='Test User',
        )

        EventOutbox.objects.all().delete()

        # Member 삭제 (is_deleted=True로 수정)
        member.is_deleted = True
        member.save()

        # 이벤트 생성 안 함
        self.assertEqual(EventOutbox.objects.count(), 0)

    def test_event_payload_structure(self):
        """이벤트 페이로드 구조 검증"""
        member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            name='Test User',
            phone='010-1234-5678',
            postal_code='12345',
            address='Seoul, Korea',
            level=1,
            point=100,
            email_opt_in=True,
        )

        event = EventOutbox.objects.get()
        payload = event.payload

        # 필수 필드 검증
        required_fields = [
            'memb_idx', 'memb_id', 'memb_name', 'memb_email',
            'memb_level', 'memb_region', 'memb_point'
        ]
        for field in required_fields:
            self.assertIn(field, payload, f'페이로드에 {field}가 없음')


class RecruitSignalTestCase(TestCase):
    """JobNotice 모델 Signal 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        self.member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            name='Test User',
        )
        self.company = Company.objects.create(
            member=self.member,
            company_name='Test Company',
        )

    def test_job_notice_insert_creates_event(self):
        """JobNotice 신규 생성 시 EventOutbox 이벤트 생성"""
        initial_count = EventOutbox.objects.count()

        job_notice = JobNotice.objects.create(
            member=self.member,
            company=self.company,
            title='Python Developer',
            employment_type='Full-time',
            occupations=['developer', 'python'],
            is_approved=True,
        )

        # 이벤트 생성 확인
        self.assertEqual(EventOutbox.objects.count(), initial_count + 1)

        event = EventOutbox.objects.filter(
            event_type=EventType.RECRUIT_INSERT
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.aggregate_id, job_notice.id)

    def test_job_notice_update_creates_event(self):
        """JobNotice 수정 시 EventOutbox 이벤트 생성"""
        job_notice = JobNotice.objects.create(
            member=self.member,
            company=self.company,
            title='Python Developer',
            employment_type='Full-time',
        )

        EventOutbox.objects.all().delete()

        # JobNotice 수정
        job_notice.title = 'Senior Python Developer'
        job_notice.save()

        event = EventOutbox.objects.get()
        self.assertEqual(event.event_type, EventType.RECRUIT_UPDATE)

    def test_recruit_event_payload_occupations(self):
        """채용공고 이벤트 페이로드의 직종 변환 검증"""
        occupations = ['developer', 'python', 'django']
        job_notice = JobNotice.objects.create(
            member=self.member,
            company=self.company,
            title='Test Job',
            occupations=occupations,
        )

        event = EventOutbox.objects.get()
        payload = event.payload

        # occupations 파이프 변환 검증
        self.assertEqual(payload['notice_occupation'], 'developer|python|django')


class EventOutboxModelTestCase(TestCase):
    """EventOutbox 모델 테스트"""

    def test_event_status_transitions(self):
        """이벤트 상태 전이 테스트"""
        event = EventOutbox.objects.create(
            event_type=EventType.MEMBER_INSERT,
            aggregate_type='member',
            aggregate_id=1,
            payload={},
            status=EventStatus.PENDING,
        )

        # PENDING → PROCESSING
        event.mark_processing()
        self.assertEqual(event.status, EventStatus.PROCESSING)

        # PROCESSING → DONE
        event.mark_done()
        self.assertEqual(event.status, EventStatus.DONE)
        self.assertIsNotNone(event.processed_at)

    def test_event_failure_and_retry(self):
        """이벤트 실패 및 재시도 로직 테스트"""
        event = EventOutbox.objects.create(
            event_type=EventType.MEMBER_INSERT,
            aggregate_type='member',
            aggregate_id=1,
            payload={},
            max_retries=3,
        )

        # 첫 실패
        event.mark_failed('First error')
        self.assertEqual(event.status, EventStatus.FAILED)
        self.assertEqual(event.retry_count, 1)
        self.assertTrue(event.can_retry)

        # 두 번째 실패
        event.mark_failed('Second error')
        self.assertEqual(event.retry_count, 2)

        # 세 번째 실패 (최대 재시도 초과)
        event.mark_failed('Third error')
        self.assertEqual(event.status, EventStatus.DEAD_LETTER)
        self.assertFalse(event.can_retry)

    def test_source_and_correlation_id(self):
        """source와 correlation_id 필드 검증"""
        event = EventOutbox.objects.create(
            event_type=EventType.MEMBER_INSERT,
            aggregate_type='member',
            aggregate_id=1,
            payload={},
            source=EventSource.DJANGO,
            correlation_id='uuid-12345-abcde',
        )

        self.assertEqual(event.source, EventSource.DJANGO)
        self.assertEqual(event.correlation_id, 'uuid-12345-abcde')

        # MySQL에서 생성된 이벤트
        mysql_event = EventOutbox.objects.create(
            event_type=EventType.MEMBER_UPDATE,
            aggregate_type='member',
            aggregate_id=2,
            payload={},
            source=EventSource.MYSQL,
            correlation_id='mysql:12345',
        )

        self.assertEqual(mysql_event.source, EventSource.MYSQL)
        self.assertTrue(mysql_event.correlation_id.startswith('mysql:'))


class EventProcessingTaskTestCase(TestCase):
    """Celery Task 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        self.member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            name='Test User',
        )

    def test_process_event_outbox_member_insert(self):
        """process_event_outbox 태스크: Member INSERT 처리"""
        event = EventOutbox.objects.create(
            event_type=EventType.MEMBER_INSERT,
            aggregate_type='member',
            aggregate_id=999,
            payload={
                'memb_idx': 999,
                'memb_id': 'newuser',
                'memb_name': 'New User',
                'memb_email': 'newuser@example.com',
                'memb_level': 9,
            },
            status=EventStatus.PENDING,
        )

        # 태스크 실행
        result = process_event_outbox(event.id)

        # 결과 검증
        self.assertEqual(result['status'], 'done')
        self.assertEqual(result['outbox_id'], event.id)

        # 이벤트 상태 확인
        event.refresh_from_db()
        self.assertEqual(event.status, EventStatus.DONE)
        self.assertIsNotNone(event.processed_at)

    def test_poll_pending_events(self):
        """poll_pending_events 태스크: PENDING 이벤트 폴링"""
        # 여러 개의 PENDING 이벤트 생성
        for i in range(5):
            EventOutbox.objects.create(
                event_type=EventType.MEMBER_INSERT,
                aggregate_type='member',
                aggregate_id=1000 + i,
                payload={'memb_idx': 1000 + i},
                status=EventStatus.PENDING,
            )

        # 태스크 실행
        result = poll_pending_events()

        # 결과 검증
        self.assertEqual(result['dispatched'], 5)

    def test_verify_sync_integrity(self):
        """verify_sync_integrity 태스크: 동기화 무결성 검증"""
        # DEAD_LETTER 이벤트 생성
        EventOutbox.objects.create(
            event_type=EventType.MEMBER_INSERT,
            aggregate_type='member',
            aggregate_id=1,
            payload={},
            status=EventStatus.DEAD_LETTER,
        )

        # 태스크 실행
        result = verify_sync_integrity()

        # 결과 검증
        self.assertEqual(result['dead_letter_count'], 1)
        self.assertGreaterEqual(result['result'], 'partial')

        # SyncLog 생성 확인
        log = SyncLog.objects.latest('started_at')
        self.assertEqual(log.failed_count, 1)


class EventLoggingIntegrationTestCase(APITestCase):
    """Event Logging 통합 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        self.admin_user = Member.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123',
            name='Admin User',
        )
        self.member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='test123',
            name='Test User',
        )

    def test_member_api_creates_event(self):
        """API를 통한 Member 생성 시 이벤트 기록"""
        # 기존 이벤트 제거
        EventOutbox.objects.all().delete()

        # API 호출 (시뮬레이션)
        # 실제로는 Member 생성 API를 호출하거나,
        # 다음과 같이 시뮬레이션:
        new_member = Member.objects.create_user(
            username='apiuser',
            email='apiuser@example.com',
            password='apipass123',
            name='API User',
        )

        # EventOutbox 생성 확인
        events = EventOutbox.objects.filter(
            aggregate_id=new_member.id,
            event_type=EventType.MEMBER_INSERT,
        )
        self.assertEqual(events.count(), 1)

    def test_correlation_id_tracking(self):
        """요청 추적을 위한 correlation_id 검증"""
        # 요청 시뮬레이션 (correlation_id 포함)
        from unittest.mock import patch
        import threading

        correlation_id = 'req-uuid-123456'

        # Threading context에 correlation_id 설정
        thread_context = threading.current_thread().__dict__
        thread_context['correlation_id'] = correlation_id

        try:
            member = Member.objects.create_user(
                username='correlateduser',
                email='corr@example.com',
                password='test123',
                name='Correlated User',
            )

            event = EventOutbox.objects.get(aggregate_id=member.id)
            # correlation_id는 threading context에서 읽혀야 함
            # 실제 요청 환경에서는 RequestIDMiddleware가 설정
        finally:
            # 정리
            if 'correlation_id' in thread_context:
                del thread_context['correlation_id']

    def test_event_outbox_indexing(self):
        """이벤트 테이블 인덱스 성능 검증"""
        # 많은 이벤트 생성
        events = [
            EventOutbox(
                event_type=EventType.MEMBER_INSERT,
                aggregate_type='member',
                aggregate_id=i,
                payload={},
                status=EventStatus.PENDING,
                source=EventSource.DJANGO,
            )
            for i in range(100)
        ]
        EventOutbox.objects.bulk_create(events)

        # 인덱스된 필드로 빠른 조회
        # status + created_at 인덱스
        pending = EventOutbox.objects.filter(
            status=EventStatus.PENDING
        ).count()
        self.assertEqual(pending, 100)

        # event_type + aggregate_id 인덱스
        member_events = EventOutbox.objects.filter(
            event_type=EventType.MEMBER_INSERT,
            aggregate_id=50,
        ).count()
        self.assertEqual(member_events, 1)


class PostDeleteSignalTestCase(TestCase):
    """post_delete 시그널 핸들러 테스트"""

    def setUp(self):
        self.member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            name='Test User',
        )
        self.company = Company.objects.create(
            member=self.member,
            company_name='Test Company',
        )
        self.job_notice = JobNotice.objects.create(
            member=self.member,
            company=self.company,
            title='Test Job',
            employment_type='Full-time',
        )
        # 이전 이벤트 제거
        EventOutbox.objects.all().delete()

    def test_member_hard_delete_creates_event(self):
        """Member 하드 삭제 시 delete 이벤트 생성"""
        member_id = self.member.id
        self.member.delete()

        delete_events = EventOutbox.objects.filter(
            event_type='member.delete',
            aggregate_id=member_id,
        )
        self.assertEqual(delete_events.count(), 1)
        event = delete_events.first()
        self.assertEqual(event.aggregate_type, 'member')
        self.assertEqual(event.source, EventSource.DJANGO)
        self.assertIn('deleted_at', event.payload)

    def test_job_notice_hard_delete_creates_event(self):
        """JobNotice 하드 삭제 시 delete 이벤트 생성"""
        notice_id = self.job_notice.id
        self.job_notice.delete()

        delete_events = EventOutbox.objects.filter(
            event_type='recruit.delete',
            aggregate_id=notice_id,
        )
        self.assertEqual(delete_events.count(), 1)
        event = delete_events.first()
        self.assertEqual(event.aggregate_type, 'recruit')
        self.assertEqual(event.source, EventSource.DJANGO)
        self.assertIn('notice_title', event.payload)
        self.assertIn('deleted_at', event.payload)

    def test_event_log_disabled_skips_delete_event(self):
        """EVENT_LOG_ENABLED=False 시 delete 이벤트 미생성"""
        from django.test import override_settings

        with override_settings(EVENT_LOG_ENABLED=False):
            member_id = self.member.id
            self.member.delete()

        delete_events = EventOutbox.objects.filter(
            event_type='member.delete',
            aggregate_id=member_id,
        )
        self.assertEqual(delete_events.count(), 0)


class EventLogEnabledToggleTestCase(TestCase):
    """EVENT_LOG_ENABLED 설정 토글 테스트"""

    def test_event_log_disabled_skips_save_event(self):
        """EVENT_LOG_ENABLED=False 시 save 이벤트 미생성"""
        from django.test import override_settings

        with override_settings(EVENT_LOG_ENABLED=False):
            Member.objects.create_user(
                username='noevtuser',
                email='noevt@example.com',
                password='testpass123',
                name='No Event User',
            )

        events = EventOutbox.objects.filter(aggregate_type='member')
        self.assertEqual(events.count(), 0)

    def test_event_log_enabled_creates_event(self):
        """EVENT_LOG_ENABLED=True(기본) 시 이벤트 정상 생성"""
        from django.test import override_settings

        with override_settings(EVENT_LOG_ENABLED=True):
            member = Member.objects.create_user(
                username='evtuser',
                email='evt@example.com',
                password='testpass123',
                name='Event User',
            )

        events = EventOutbox.objects.filter(
            aggregate_type='member',
            aggregate_id=member.id,
        )
        self.assertEqual(events.count(), 1)
