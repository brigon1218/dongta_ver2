# PDCA Iterator Memory

## Project: dongta-django (PHP→Django 마이그레이션)

### 핵심 파일 경로
- Design 문서: `/Volumes/sk-p31/workspace/vibe_coding/work_01/docs/02-design/features/마이그레이션.design.md`
- 프로젝트 루트: `/Volumes/sk-p31/workspace/vibe_coding/work_01/dongta-django/`
- accounts 앱 (완성 기준): `apps/accounts/`
- core/utils.py: `core/utils.py` — `success_response()`, `error_response()`
- core/models.py: `core/models.py` — `BaseModel` (soft_delete 포함)
- config/urls.py: 이미 모든 앱 URL 등록 완료

### 코딩 컨벤션
- 모든 view는 `success_response()` / `error_response()` 사용 (core.utils)
- 소프트 삭제: `instance.soft_delete()` (BaseModel 제공)
- 권한 에러: `error_response('PERM_001', '권한이 없습니다.', http_status=403)`
- 포인트 부족: `error_response('PAY_001', ..., http_status=400)`
- Rate Limit: `@method_decorator(ratelimit(...), name='post')` 클래스 데코레이터 방식

### 구현 완료 앱 (2026-03-02)
- business114: models, serializers, views, urls
- recruit: models, serializers, views, urls
- payment: models, serializers, views, urls
- accounts/views.py: LoginView에 Rate Limit (5/m, IP 기준) 추가
- nginx/nginx.conf: 하이브리드 운영 (/api/v1/* → Django:8000, /* → PHP:80)

### 구현 완료 앱 (2026-03-06) — 하이브리드_연동 Phase 2-2
- apps/sync: EventOutbox 모델, Celery Tasks, views, urls, migrations/0001_initial.py
- apps/sync/management/commands/verify_sync.py: 동기화 검증 커맨드
- config/celery.py: CELERY_QUEUES(sync/payment/default), TASK_ROUTES, BEAT_SCHEDULE 완성
- config/settings/base.py: apps.sync + django_celery_beat INSTALLED_APPS 추가, CELERY_* 환경변수 보완
- config/settings/production.py: apps.sync, celery 로거 추가
- config/urls.py: /api/v1/sync/ 등록
- docker-compose.yml: celery-sync(2 replicas), celery-payment(1 replica), celery-beat 추가
- nginx/nginx.conf: Rate Limiting(login 5r/m, api 100r/m), SSL OCSP Stapling 추가
- scripts/01_create_event_outbox.sql: TBL_EVENT_OUTBOX + 3개 트리거
- requirements/base.txt: django-celery-beat, kombu, pymysql 추가

### Match Rate 90% 달성 (2026-03-06) — 하이브리드_연동 최종
- apps/sync/tasks.py: clean_old_event_logs 태스크 추가 (매일 02:00, 7일 이상 DONE EventOutbox + SyncLog 삭제)
- config/celery.py: clean_old_event_logs task_routes 및 beat_schedule 'clean-old-event-logs-daily' 등록
- nginx/nginx.conf: ssl_stapling_responder + ssl_trusted_certificate 경로를 letsencrypt 경로로 수정

### EventOutbox 모델 주요 필드
- status: EventStatus.DONE (processed=True 에 해당)
- processed_at: DONE 상태로 전환 시점 (clean_old_event_logs 기준 필드)
- Design 문서 `processed=True` → 실제 코드 `status=EventStatus.DONE`으로 매핑

### Celery 큐 구성
- sync: 회원/업체 동기화 (process_event_outbox, poll_pending_events, verify_sync_integrity, clean_old_event_logs)
- payment: 결제 동기화 (향후)
- default: 기타

### 주의사항
- 빈 파일(1줄)도 Read 필수 (Write 전 Read 규칙)
- PointAccount는 BaseModel이 아닌 models.Model 상속 (디자인 스펙)
- `select_for_update()`로 포인트 차감 시 race condition 방지
