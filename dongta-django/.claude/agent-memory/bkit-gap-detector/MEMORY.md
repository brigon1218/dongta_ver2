# Gap Detector Memory

## Project Context
- Project: dongta.com PHP+MySQL -> Django+PostgreSQL migration
- Level: Enterprise
- Design docs: /Volumes/sk-p31/workspace/vibe_coding/work_01/docs/02-design/features/
- Implementation: /Volumes/sk-p31/workspace/vibe_coding/work_01/dongta-django/apps/

## Completed Analyses

### 1. Migration Feature (Phase 1)
- Match Rate: 73% -> 94% (1 iteration)
- Status: Completed, Reported

### 2. Hybrid Integration (Phase 2)
- Match Rate: 93%
- Status: Archived (docs/archive/2026-03/)

### 3. Danal Payment Integration (Phase 2-3)
- v1.0: 87% (P0: 2, P1: 4)
- v2.0: 97% (P0: 0, P1: 0, P2: 3, P3: 5)
- Key fixes: HMAC mandatory, PaymentService layer, IP whitelist, migration file
- Remaining: Celery task test, danal/__init__.py, DanalCallbackSerializer unused, admin.py, design doc updates
- Status: Ready for report phase

## Key Patterns
- Design docs path differs from django project root (docs/ is at work_01/ level, not dongta-django/)
- Payment app uses PaymentService as service layer (View -> PaymentService -> DanalClient)
- Error codes: PAY_001 (points), PAY_002 (server), PAY_003 (validation), PAY_005 (security)
