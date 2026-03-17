# Gap Detector Agent Memory

## Project: dongta.com

### Key Paths
- Design docs: `docs/02-design/features/`
- Analysis output: `docs/03-analysis/features/`
- Nginx config: `config/nginx/`
- Systemd config: `systemd/`
- Deploy scripts: `scripts/`
- Django project: `dongta-django/`
- Django apps: `dongta-django/apps/`
- Celery config: `dongta-django/config/celery.py`
- Docker Compose: `dongta-django/docker-compose.yml`

### Analysis History
- 2026-03-06 v0.1: 하이브리드_연동 gap analysis - Overall 49%
- 2026-03-06 v1.1: Re-analysis after auto-improvement - Overall 88% (+39%)
  - Phase 2-1 (Nginx/Systemd/Deploy): ~93% complete
  - Phase 2-2 (Celery/MySQL Trigger/Sync Tasks): ~94% complete
  - Phase 2-3 (Payment/Danal): 0% (not yet scheduled)
  - Remaining for 90%: SSL OCSP Stapling, Rate Limiting, clean_old_event_logs Task
  - Details: `docs/03-analysis/features/하이브리드_연동.analysis.md`
- 2026-03-07 v1.1: 전체_최적화_및_배포 gap analysis - Overall 95% (ARCHIVED 2026-03-09)
  - Archive: `docs/archive/2026-03/전체_최적화_및_배포/`
- 2026-03-07 v1.0: 다날_결제_통합 gap analysis - Overall 87%
  - Architecture: 80% (Service layer missing, View calls DanalClient directly)
  - Data Model: 100%
  - API Spec: 100%
  - Security: 70% (HMAC bypass when signature absent, IP whitelist missing)
  - Async Sync: 100%
  - Testing: 85% (Celery task unit test missing)
  - P0: makemigrations not run, HMAC signature bypass
  - P1: IP whitelist, PaymentService layer, requirements deps, PAY_004 mismatch
  - Details: `docs/03-analysis/features/다날_결제_통합.analysis.md`

### Patterns
- Design doc structure: Sections 2.x = Architecture, 3.x = Data Sync, 4.x = Payment, 5.x = Monitoring, 6.x = Deploy, 7.x = Security
- Implementation files are split between project root (config/, systemd/, scripts/) and dongta-django/ subdirectory
- MySQL trigger SQL at: `dongta-django/scripts/01_create_event_outbox.sql`
- apps/sync/ fully implemented (models, tasks, views, serializers, urls, management command, migration)
- apps/payment/ fully implemented (models, views, serializers, tasks, danal/client.py, danal/config.py, tests, urls)
- Design uses simplified column names (NO_MEMB, ID_MEMBER) but actual DB uses memb_idx, memb_id etc.
- Phase 2.1 design structure: S2=Architecture, S3=Data Model, S4=API Spec, S5=Auth Bridge, S6=Event Logging, S7=Monitoring, S8=Nginx, S9=Security, S10=Test Plan, S11=Impl Order, S13=Env Vars
- apps/monitoring/ fully implemented (apps.py, middleware.py, views.py, urls.py, permissions.py, tests/test_monitoring.py)
- BridgeRevokeView implementation diverges from design (IsAuthenticated vs AllowAny, different body params)
- Implementation improved Design's boolean `processed` to 5-state EventStatus enum
- 2026-03-10 v1.0: 마이그레이션_부가기능 gap analysis - Overall 90%
  - Password Reset: 2-step flow implemented (design only had 1 endpoint)
  - Social Login: Design GET x2 -> Implementation POST x1 unified (better)
  - P1: Celery Beat schedule missing for cleanup task, FRONTEND_URL not in .env.example
  - P2: Email enumeration, rate limit on reset, unused allauth/social-auth deps
  - Details: `docs/03-analysis/features/마이그레이션_부가기능.analysis.md`
  - apps/accounts/ now has: models, serializers, views, urls, tasks, hashers, migrations(0001+0002), tests, templates
- 2026-03-17 v3.0: 마이그레이션 full re-analysis - Overall 88%
  - Added S6(Error Handling), S9(Clean Architecture), S10(Convention) categories
  - Architecture: 93%, Data Model: 97%, API: 90%, Security: 95%
  - Test Coverage: 65% (strict: 3 apps completely untested - business114, recruit, mypage)
  - All Design S4.2 accounts APIs now implemented (password reset + social login)
  - Admin REST APIs remain as Django Admin actions only (4 endpoints not exposed as REST)
  - MyFolder/MyData models still empty in mypage/models.py
  - P1: Add tests for 3 apps, MyFolder/MyData models, PaymentAdmin, verify.py, Admin APIs
  - Details: `docs/03-analysis/features/마이그레이션.analysis.md`
- 2026-03-17 v1.0: PHP_Django_하이브리드_연동_2.1 gap analysis - Overall 83%
  - API Spec: 72% (bridge/refresh missing, monitoring/auth URL mismatch, event retry in wrong app)
  - Data Model: 90% (EventSource 'php' vs 'mysql' naming, MySQL DDL lacks source/correlation_id)
  - Middleware/Auth: 92% (near complete, bonus features added)
  - Monitoring: 68% (simplified responses vs rich design spec)
  - Event Logging: 88% (richer payload than design, recruit triggers missing from SQL)
  - Test Coverage: 70% (bridge tests completely absent - P0)
  - Architecture: 100%, Convention: 93%
  - P0: Bridge unit tests, BridgeRevokeView permission/contract mismatch
  - P1: bridge/refresh URL, MySQL DDL update, recruit triggers, sync admin.py
  - Projected 93% after P0+P1 fixes
  - Details: `docs/03-analysis/features/PHP_Django_하이브리드_연동_2.1.analysis.md`
