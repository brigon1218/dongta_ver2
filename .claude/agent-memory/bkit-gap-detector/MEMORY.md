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
- Implementation improved Design's boolean `processed` to 5-state EventStatus enum
- 2026-03-10 v1.0: 마이그레이션_부가기능 gap analysis - Overall 90%
  - Password Reset: 2-step flow implemented (design only had 1 endpoint)
  - Social Login: Design GET x2 -> Implementation POST x1 unified (better)
  - P1: Celery Beat schedule missing for cleanup task, FRONTEND_URL not in .env.example
  - P2: Email enumeration, rate limit on reset, unused allauth/social-auth deps
  - Details: `docs/03-analysis/features/마이그레이션_부가기능.analysis.md`
  - apps/accounts/ now has: models, serializers, views, urls, tasks, hashers, migrations(0001+0002), tests, templates
