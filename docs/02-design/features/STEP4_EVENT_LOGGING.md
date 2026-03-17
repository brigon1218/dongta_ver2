# Step 4: Event Logging (이벤트 로깅)

**Phase**: 2.1 - PHP ↔ Django 하이브리드 연동
**Status**: ✅ Implementation Complete
**Date**: 2026-03-17

## 개요

Step 4는 양방향 이벤트 로깅 인프라를 구축하여 MySQL과 PostgreSQL 간의 데이터 동기화를 실현한다.

### 동기화 방향

```
Django (PostgreSQL)                    MySQL (PHP)
    ↓                                      ↓
Signal Handlers                     Triggers + Events
    ↓                                      ↓
EventOutbox (source=DJANGO)  ←→  EventOutbox (source=MYSQL)
    ↓                                      ↓
process_event_outbox         process_php_events
    ↓                                      ↓
PostgreSQL 반영              ← Celery Polling →  PostgreSQL 반영
```

## 구현 사항

### 1. 모델 확장: EventSource & 필드 추가

**파일**: `apps/sync/models.py`

```python
class EventSource(models.TextChoices):
    DJANGO = 'django', 'Django 시스템'
    MYSQL = 'mysql', 'MySQL 레거시 시스템'

class EventOutbox(models.Model):
    # 기존 필드들...
    source = CharField(choices=EventSource.choices, default=EventSource.MYSQL)
    correlation_id = CharField(max_length=100, blank=True)  # X-Request-ID 추적
```

**마이그레이션**: `0002_eventsource_fields.py`
- source 필드: 이벤트 발생 시스템 구분 (Django vs MySQL)
- correlation_id 필드: 요청 추적을 위한 X-Request-ID (RequestIDMiddleware와 연계)

### 2. Django Signal Handlers

**파일**: `apps/sync/signals.py` (새로 생성)

#### 2.1 Member Signal Handler

```python
@receiver(post_save, sender='accounts.Member')
def create_member_event(sender, instance, created, **kwargs):
    """Member 생성/수정 시 EventOutbox에 이벤트 기록"""
    event_type = EventType.MEMBER_INSERT if created else EventType.MEMBER_UPDATE
    payload = { ... }  # 회원 데이터 매핑

    EventOutbox.objects.create(
        event_type=event_type,
        aggregate_type='member',
        aggregate_id=instance.id,
        payload=payload,
        source=EventSource.DJANGO,
        correlation_id=_get_correlation_id(),  # 요청 추적
    )
```

**처리 흐름**:
1. Member.post_save 신호 수신
2. EventOutbox에 event_type = MEMBER_INSERT/UPDATE로 기록
3. source = DJANGO, correlation_id = 현재 요청의 X-Request-ID
4. payload에 회원 정보 JSON 저장

#### 2.2 JobNotice Signal Handler

```python
@receiver(post_save, sender='recruit.JobNotice')
def create_recruit_event(sender, instance, created, **kwargs):
    """JobNotice 생성/수정 시 EventOutbox에 이벤트 기록"""
    # Member와 유사한 로직
    # occupations 리스트 → 파이프 구분자(|)로 변환하여 MySQL 형식으로 저장
```

### 3. Signal 등록

**파일**: `apps/sync/apps.py`

```python
class SyncConfig(AppConfig):
    def ready(self):
        import apps.sync.signals  # Signal handlers 자동 등록
```

앱 시작 시 signals.py를 임포트하여 모든 @receiver 데코레이터가 등록된다.

### 4. Celery Tasks: 양방향 이벤트 폴링

#### 4.1 process_php_events (MySQL → Django)

**파일**: `apps/sync/tasks.py`

```python
@shared_task(queue='sync', name='apps.sync.tasks.process_php_events')
def process_php_events():
    """
    MySQL TBL_EVENT_OUTBOX에서 PENDING 상태 이벤트를 폴링하여
    PostgreSQL EventOutbox로 마이그레이션한다.
    """
    # 1. MySQL에서 PENDING 이벤트 조회 (최대 100개)
    # 2. _create_outbox_from_mysql()으로 PostgreSQL에 복제
    # 3. correlation_id = 'mysql:{event_id}' (중복 방지)
    # 4. MySQL 상태 업데이트 (PROCESSED)
```

**호출 주기**: Celery Beat에서 5분마다 실행

#### 4.2 process_event_outbox (기존 - PostgreSQL 이벤트 처리)

```python
@shared_task(queue='sync')
def process_event_outbox(outbox_id):
    """
    EventOutbox의 PENDING 이벤트를 처리하여
    해당 데이터를 PostgreSQL 또는 MySQL에 동기화한다.
    """
    # 1. 이벤트 상태 PENDING → PROCESSING
    # 2. event_type에 따라 적절한 핸들러 호출
    # 3. 성공 시 상태 DONE, 실패 시 재시도 또는 DLQ
```

**호출 방식**:
- `poll_pending_events()`: PENDING 이벤트 배치 폴링 (5분마다)
- 각 이벤트마다 `process_event_outbox.apply_async()` 발행

### 5. Celery Beat 스케줄

**파일**: `config/settings/base.py`

```python
CELERY_BEAT_SCHEDULE = {
    'poll-pending-events': {
        'task': 'apps.sync.tasks.poll_pending_events',
        'schedule': crontab(minute='*/5'),  # 5분 주기
    },
    'process-php-events': {
        'task': 'apps.sync.tasks.process_php_events',
        'schedule': crontab(minute='*/5'),  # 5분 주기 (MySQL 폴링)
    },
    'verify-sync-integrity': {
        'task': 'apps.sync.tasks.verify_sync_integrity',
        'schedule': crontab(minute=0),  # 매시간 (무결성 검증)
    },
    'clean-old-event-logs': {
        'task': 'apps.sync.tasks.clean_old_event_logs',
        'schedule': crontab(hour=2, minute=0),  # 매일 2AM (7일 이상 된 로그 정리)
    },
}
```

### 6. MySQL DDL & Triggers

**파일**: `dongta.mysql/02_event_outbox_ddl.sql`

#### 6.1 TBL_EVENT_OUTBOX 테이블

```sql
CREATE TABLE TBL_EVENT_OUTBOX (
    event_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id BIGINT NOT NULL,
    payload_json LONGTEXT NOT NULL,
    status ENUM('PENDING', 'PROCESSED', 'FAILED') DEFAULT 'PENDING',
    retry_count SMALLINT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE,

    KEY idx_status_created (status, created_at),
    KEY idx_event_type_aggregate (event_type, aggregate_id)
);
```

#### 6.2 Trigger: trg_member_insert & trg_member_update

```sql
CREATE TRIGGER trg_member_insert AFTER INSERT ON TBL_MEMB
FOR EACH ROW
BEGIN
    INSERT INTO TBL_EVENT_OUTBOX (event_type, ..., payload_json)
    VALUES ('member.insert', ..., JSON_OBJECT(...));
END;
```

PHP 관리자가 TBL_MEMB를 수정하면 자동으로 TBL_EVENT_OUTBOX에 이벤트가 기록된다.

#### 6.3 Trigger: trg_jobnotice_insert & trg_jobnotice_update

유사하게 TBL_JOBNOTICE 변경 시 recruitment 관련 이벤트를 기록한다.

#### 6.4 정리 프로시저

```sql
CREATE PROCEDURE sp_cleanup_processed_events(IN p_keep_hours INT)
BEGIN
    DELETE FROM TBL_EVENT_OUTBOX
    WHERE status = 'PROCESSED'
      AND updated_at < DATE_SUB(NOW(), INTERVAL p_keep_hours HOUR);
END;
```

정기적으로 처리 완료된 이벤트를 삭제하여 테이블 크기를 유지한다.

## 요청 추적 (Correlation ID)

### 요청 흐름

```
1. Client Request
   ↓
2. RequestIDMiddleware:
   - X-Request-ID 헤더 확인 또는 UUID 생성
   - request.correlation_id 설정
   ↓
3. SessionBridgeMiddleware / View 처리
   ↓
4. Member/JobNotice 저장
   ↓
5. Signal Handler:
   - _get_correlation_id()로 현재 요청의 correlation_id 조회
   - EventOutbox.correlation_id에 저장
   ↓
6. EventOutbox에 correlation_id 기록됨
   - 로그에서 요청 흐름 추적 가능
   - MySQL에서 발생한 이벤트: correlation_id = 'mysql:{event_id}'
```

### 사용 예시

```python
# 로그에서 특정 요청의 모든 이벤트 조회
from apps.sync.models import EventOutbox

correlation_id = 'req-uuid-abc123'
events = EventOutbox.objects.filter(correlation_id=correlation_id)

for event in events:
    print(f"{event.event_type} at {event.created_at}")
```

## 이벤트 처리 상태 다이어그램

```
PENDING
  ↓
  ├─→ process_event_outbox() 실행
  │   ├─→ 성공 → DONE (processed_at 기록)
  │   └─→ 실패 → FAILED (재시도)
  │
  └─→ 재시도 횟수 < max_retries
      └─→ FAILED → (다음 폴링 시) PENDING

  재시도 횟수 >= max_retries
  └─→ DEAD_LETTER (수동 개입 필요, 모니터링)
```

## 테스트

**파일**: `apps/sync/tests/test_event_logging.py`

### 테스트 케이스

1. **MemberSignalTestCase**
   - test_member_insert_creates_event: Member 생성 시 이벤트 생성
   - test_member_update_creates_event: Member 수정 시 이벤트 생성
   - test_deleted_member_no_event: 삭제된 Member는 이벤트 생성 안 함
   - test_event_payload_structure: 페이로드 구조 검증

2. **RecruitSignalTestCase**
   - test_job_notice_insert_creates_event
   - test_job_notice_update_creates_event
   - test_recruit_event_payload_occupations

3. **EventOutboxModelTestCase**
   - test_event_status_transitions: PENDING → PROCESSING → DONE
   - test_event_failure_and_retry: 실패 및 재시도 로직
   - test_source_and_correlation_id: 필드 검증

4. **EventProcessingTaskTestCase**
   - test_process_event_outbox_member_insert
   - test_poll_pending_events
   - test_verify_sync_integrity

5. **EventLoggingIntegrationTestCase**
   - test_member_api_creates_event: API를 통한 이벤트 생성
   - test_correlation_id_tracking: 요청 추적
   - test_event_outbox_indexing: 인덱싱 성능

### 테스트 실행

```bash
# 모든 이벤트 로깅 테스트
python manage.py test apps.sync.tests.test_event_logging

# 특정 테스트 클래스
python manage.py test apps.sync.tests.test_event_logging.MemberSignalTestCase

# 특정 테스트 메서드
python manage.py test apps.sync.tests.test_event_logging.MemberSignalTestCase.test_member_insert_creates_event
```

## 모니터링

### 중요 메트릭

1. **PENDING 이벤트 수**
   ```python
   from apps.sync.models import EventOutbox, EventStatus
   pending = EventOutbox.objects.filter(status=EventStatus.PENDING).count()
   ```

2. **DEAD_LETTER 이벤트 (실패한 이벤트)**
   ```python
   dlq = EventOutbox.objects.filter(status=EventStatus.DEAD_LETTER).count()
   ```

3. **처리 시간**
   ```python
   from django.utils import timezone
   slow_processing = EventOutbox.objects.filter(
       status=EventStatus.DONE,
       processed_at__gt=timezone.now() - timedelta(minutes=5)
   ).annotate(
       processing_time=F('processed_at') - F('created_at')
   ).filter(processing_time__gt=timedelta(seconds=10))
   ```

### 대시보드 구현 (선택사항)

모니터링 앱의 EventStatusView에서 이벤트 통계를 제공할 수 있다.

```python
class EventStatusView(APIView):
    def get(self, request):
        return Response({
            'total_events': EventOutbox.objects.count(),
            'pending_events': EventOutbox.objects.filter(status=EventStatus.PENDING).count(),
            'dlq_events': EventOutbox.objects.filter(status=EventStatus.DEAD_LETTER).count(),
            'hourly_processing_rate': ...,
        })
```

## 주의사항

1. **중복 이벤트 처리**
   - MySQL에서 발생한 이벤트: `correlation_id = 'mysql:{event_id}'`로 중복 방지
   - Django Signal: 같은 인스턴스의 중복 save() 호출 시 여러 이벤트 생성 가능

2. **성능**
   - EventOutbox 테이블이 커질 수 있으므로 정기적 정리 필수
   - `clean_old_event_logs` 태스크가 7일 이상 된 로그를 자동 삭제

3. **재시도 전략**
   - Celery 자동 재시도 + EventOutbox.mark_failed()의 이중 재시도
   - 최대 재시도 횟수를 초과하면 DEAD_LETTER로 이동
   - 수동 개입 필요: 원인 분석 후 상태 PENDING으로 복구 가능

4. **데이터 순서**
   - EventOutbox는 생성일시 기준으로 정렬됨
   - 복잡한 트랜잭션에서 순서 보장 필수 시 correlation_id 활용

## 다음 단계

Step 5: E2E Testing & Staging Deployment

- E2E 시나리오 테스트
- 부하 테스트 (k6)
- 72시간 안정성 검증
- 프로덕션 배포 체크리스트

---

**마지막 수정**: 2026-03-17
**담당**: AI Assistant
**상태**: ✅ 완료
