# Phase 5: 배포 후 성능 최적화 및 운영 안정화 계획 문서

> **Summary**: 운영 환경 배포 후 캐싱, 모니터링, 카나리 배포, 슬로우 쿼리 최적화를 통해 99.9% 가용성과 500ms 이하 응답시간을 달성한다.
>
> **Project**: dongta.com (PHP+MySQL → Django+PostgreSQL 마이그레이션)
> **Version**: 5.0
> **Author**: Product Manager
> **Date**: 2026-03-09
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

Phase 3 완료(95% 일치도) 이후 운영 환경에서 발생하는 성능 병목, 가용성 리스크, 모니터링 공백을 해소한다. View-level 캐싱, Prometheus 메트릭 수집, Grafana 대시보드, Canary 배포 전략, 슬로우 쿼리 분석을 순차적으로 적용하여 서비스 품질을 운영 수준으로 끌어올린다.

### 1.2 Background

- Phase 1–3를 통해 Django+PostgreSQL 스택 전환 및 다날 결제 통합이 완료되었다.
- 코드 레벨 준비는 완료되었으나, 실제 트래픽을 받는 운영 환경에서의 성능 보장 체계가 미비하다.
- PHP 레거시와 병행 운영(하이브리드 모드) 기간 동안 예상치 못한 부하 패턴이 발생할 수 있다.
- 배포 중 장애를 최소화하기 위한 점진적 트래픽 전환(Canary) 전략이 필요하다.
- 현재 Redis, Celery, Nginx 인프라가 이미 구성되어 있어 추가 인프라 비용 없이 최적화를 적용할 수 있다.

### 1.3 Related Documents

- Phase 3 Plan: `docs/01-plan/features/전체_최적화_및_배포.plan.md` (Archived)
- Phase 3 Report: `docs/04-report/features/마이그레이션-v2.report.md`
- 하이브리드 연동 Archive: `docs/archive/2026-03/하이브리드_연동/`
- 다날 결제 통합 Design: `docs/02-design/features/다날_결제_통합.design.md`

---

## 2. Scope

### 2.1 In Scope

- [x] View-level caching (`@cache_page`) 적용 — recruit, business114 목록/상세 API
- [x] Prometheus metrics 수집 설정 (CPU, Memory, DB query time, Request latency)
- [x] Grafana 대시보드 구성 (실시간 모니터링, 알림 룰)
- [x] Canary 배포 전략 구현 (10% → 50% → 100% 트래픽 전환)
- [x] Slow query 탐지 및 쿼리 최적화 (인덱스 추가, N+1 해소)
- [x] Connection pool 설정 최적화 (min: 5, max: 20)
- [x] APM 통합 — django-debug-toolbar(개발), New Relic(운영, 선택사항)
- [x] Nginx upstream health check 설정
- [x] Staging 환경 검증 (1주)

### 2.2 Out of Scope

- 마이크로서비스 분해 (Phase 6 이후 검토)
- 새로운 비즈니스 기능 추가 (신규 API, 새 페이지)
- 데이터 마이그레이션 (Phase 1–3에서 완료)
- CDN 도입 (정적 파일 배포 체계 개선은 별도 Phase로 분리)
- Kubernetes / 서비스 메쉬 도입 (현 규모에서 불필요)
- OAuth2 소셜 로그인, 비밀번호 재설정 이메일 (별도 Plan 필요)

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | 요구사항 | Priority | Status |
|----|----------|----------|--------|
| FR-01 | recruit 및 business114 목록/상세 API에 `@cache_page` 데코레이터를 적용하고 TTL을 설정한다 | Must | Pending |
| FR-02 | Prometheus exporter를 Django에 통합하여 CPU, Memory, DB 쿼리 시간, Request latency를 수집한다 | Must | Pending |
| FR-03 | Grafana 대시보드를 구성하여 실시간 메트릭 시각화 및 임계값 초과 시 알림(Alert)을 발송한다 | Must | Pending |
| FR-04 | Nginx weighted routing을 이용한 Canary 배포를 구현한다 (10% → 50% → 100% 단계별 트래픽 전환) | Must | Pending |
| FR-05 | Django ORM slow query 로그(`CONN_MAX_AGE`, `django-silk` 또는 `pgBadger`)를 분석하여 응답시간 50% 감소 대상 쿼리를 식별하고 최적화한다 | Must | Pending |
| FR-06 | django-debug-toolbar(개발 환경) 및 선택적으로 New Relic(운영 환경)을 통해 APM 프로파일링을 구성한다 | Should | Pending |
| FR-07 | Nginx upstream 블록에 health check 지시자를 추가하여 비정상 인스턴스를 자동 제외한다 | Should | Pending |
| FR-08 | Cache hit rate를 `/metrics` 엔드포인트 또는 Grafana에서 실시간으로 확인할 수 있도록 한다 | Should | Pending |
| FR-09 | Celery 작업 큐 지연(lag) 및 worker 처리량을 Prometheus에서 수집한다 (Celery exporter 활용) | Could | Pending |
| FR-10 | Blue-Green 배포 스크립트를 작성하여 무중단 전환을 자동화한다 | Could | Pending |

### 3.2 Non-Functional Requirements

| Category | 기준 | 측정 방법 |
|----------|------|-----------|
| Performance | 응답시간 p95 < 500ms | Prometheus histogram + Grafana |
| Availability | API 가용성 > 99.9% | Prometheus uptime metric |
| Cache | 목록 API cache hit rate > 70% | Redis INFO stats / Prometheus |
| Database | DB connection pool min: 5, max: 20 | django-db-geventpool 설정 확인 |
| Resource | 피크 트래픽 시 CPU 사용률 < 70% | Prometheus node exporter |
| Deployment | Canary 배포 중 오류율 < 0.1% | Nginx access log + Grafana |
| Query | Slow query 응답시간 50% 감소 | pg_stat_statements 비교 |
| Observability | 모든 핵심 API 엔드포인트에 메트릭 계측 | Prometheus scrape 확인 |

---

## 4. Architecture Components

### 4.1 Caching Layer

```
Client Request
      ↓
  Nginx (upstream)
      ↓
  Django View
      ↓
  @cache_page (TTL 설정)
      ↓
  Redis (기존 docker-compose.prod.yml 재사용)
```

- Redis: 이미 구성된 인프라 재사용 (`REDIS_URL` 환경변수로 연결)
- 캐시 키: URL 기반 자동 생성 (`@cache_page(timeout=300)`)
- 캐시 무효화: 데이터 변경 signal 또는 수동 Celery task로 처리

### 4.2 Metrics Collection

```
Django App
  ├── django-prometheus (request/response 메트릭)
  ├── Celery Exporter (큐 지연, worker 처리량)
  └── Node Exporter (CPU, Memory, Disk)
        ↓
  Prometheus (scrape interval: 15s)
        ↓
  Grafana (대시보드 + AlertManager)
```

### 4.3 Canary Deployment

```
Nginx (Load Balancer)
  ├── upstream django_stable  (가중치: 90%)
  └── upstream django_canary  (가중치: 10% → 50% → 100%)

단계별 전환:
  Week 3-1: 10% 트래픽 → Canary 인스턴스
  Week 3-2: 오류율 정상 확인 → 50% 전환
  Week 3-3: 안정성 확인 → 100% 전환 완료
```

### 4.4 Database Optimization

- Connection pool: `CONN_MAX_AGE = 60` (Django 기본값 → 커스텀 pool로 교체 검토)
- Slow query: `pg_stat_statements` 확성화 → 상위 10개 쿼리 최적화
- Index: `EXPLAIN ANALYZE` 기반으로 누락 인덱스 식별 및 추가
- N+1: `select_related` / `prefetch_related` 적용

---

## 5. Implementation Roadmap

### Week 1: Staging 배포 및 Caching 설정

| 항목 | 담당 | 완료 기준 |
|------|------|-----------|
| Staging 환경 Docker Compose 구성 | Backend | `docker-compose.staging.yml` 실행 정상 |
| `@cache_page` 적용 — recruit 목록/상세 | Backend | cache hit 확인 (Redis Monitor) |
| `@cache_page` 적용 — business114 목록/상세 | Backend | cache hit 확인 |
| Connection pool 설정 (`CONN_MAX_AGE`) | Backend | DB 커넥션 수 모니터링 |
| Slow query 로그 활성화 | DevOps | `pg_stat_statements` 활성화 확인 |

### Week 2: Prometheus + Grafana 연동

| 항목 | 담당 | 완료 기준 |
|------|------|-----------|
| `django-prometheus` 설치 및 `/metrics` 엔드포인트 노출 | Backend | Prometheus scrape 성공 |
| Celery Exporter 설정 | DevOps | Celery 큐 메트릭 수집 확인 |
| Node Exporter 추가 | DevOps | CPU/Memory 메트릭 수집 확인 |
| Grafana 대시보드 구성 (Django, Celery, System) | DevOps | 대시보드 패널 정상 표시 |
| Alert 룰 설정 (응답시간 > 500ms, 오류율 > 1%) | DevOps | 테스트 알림 발송 확인 |

### Week 3: Canary 배포 (10% → 100%)

| 항목 | 담당 | 완료 기준 |
|------|------|-----------|
| Nginx weighted upstream 설정 | DevOps | 10% 트래픽 Canary 인스턴스 전달 확인 |
| Canary 10% 배포 및 모니터링 (2일) | DevOps | 오류율 < 0.1% 유지 |
| 50% 전환 및 모니터링 (2일) | DevOps | 오류율 < 0.1%, 응답시간 < 500ms 유지 |
| 100% 전환 완료 | DevOps | 전체 트래픽 신규 인스턴스 처리 확인 |
| Nginx health check 설정 | DevOps | 비정상 인스턴스 자동 제외 확인 |

### Week 4: 성능 튜닝 및 최적화

| 항목 | 담당 | 완료 기준 |
|------|------|-----------|
| Slow query Top 10 분석 및 최적화 | Backend | 해당 쿼리 응답시간 50% 감소 |
| N+1 쿼리 식별 및 `select_related` 적용 | Backend | ORM 쿼리 수 감소 확인 |
| APM 통합 (django-debug-toolbar 개발 환경) | Backend | 프로파일링 UI 정상 동작 |
| Cache hit rate 검증 (> 70% 목표) | Backend | Grafana 또는 Redis INFO로 확인 |
| 최종 부하 테스트 (locust 또는 k6) | QA | p95 < 500ms, 오류율 < 0.1% |

---

## 6. Success Criteria

### 6.1 Definition of Done

- [x] 모든 Must 기능 요구사항(FR-01 ~ FR-05) 구현 완료
- [x] Staging 환경에서 부하 테스트 통과 (p95 < 500ms)
- [x] Canary 배포 3단계 완료 (오류율 < 0.1% 유지)
- [x] Grafana 대시보드에서 실시간 메트릭 확인 가능
- [x] Slow query 응답시간 50% 이상 감소 검증
- [x] 운영 가이드 문서 작성 완료

### 6.2 Quality Criteria

- [x] Cache hit rate > 70% (recruit, business114 목록 API)
- [x] API 가용성 > 99.9% (운영 환경 Week 4 기준)
- [x] CPU 사용률 피크 < 70%
- [x] Prometheus metrics scrape 성공률 100%
- [x] 배포 중 다운타임 0초 (Canary 전략 적용)

---

## 7. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Canary 배포 중 신규 인스턴스 오류 | High | Medium | Nginx에서 오류율 임계값(> 1%) 초과 시 자동 롤백 스크립트 준비 |
| Redis 캐시 장애 시 전체 API 중단 | High | Low | Cache backend fallthrough 설정 (`CACHE_MIDDLEWARE_ALIAS` 폴백) |
| Prometheus/Grafana 설정 오류로 모니터링 공백 | Medium | Medium | Staging 환경에서 1주간 사전 검증 후 운영 적용 |
| Slow query 최적화 후 기능 회귀 | Medium | Low | 최적화 전/후 통합 테스트 스위트 실행 (기존 30+ 테스트 활용) |
| Connection pool 설정 부적절로 DB 과부하 | High | Low | Staging에서 pool 설정 검증 후 운영 적용, `pg_stat_activity` 모니터링 |
| New Relic 라이선스 비용 | Low | Medium | 무료 티어 검토, 대안으로 django-silk (무료) 사용 |

---

## 8. Architecture Considerations

### 8.1 Project Level

| Level | Characteristics | Recommended For | Selected |
|-------|-----------------|-----------------|:--------:|
| Starter | Simple structure | Static sites, portfolios | |
| Dynamic | Feature-based modules, BaaS integration | Web apps with backend | |
| Enterprise | Strict layer separation, DI, microservices | High-traffic systems | X |

선택: **Enterprise** — 기존 프로젝트 레벨 유지

### 8.2 Key Technical Decisions

| 결정 항목 | 대안 | 선택 | 근거 |
|-----------|------|------|------|
| Caching | Memcached / Varnish / Redis | Redis | 기존 docker-compose.prod.yml에 이미 구성됨 |
| Metrics | Datadog / New Relic / Prometheus | Prometheus | 오픈소스, Django 생태계 통합 용이 (`django-prometheus`) |
| Visualization | Kibana / Datadog / Grafana | Grafana | Prometheus와 네이티브 통합, Postgres datasource 지원 |
| Deployment Strategy | Rolling / Blue-Green / Canary | Canary | 서비스 메쉬 없이 Nginx weighted routing으로 구현 가능, 점진적 위험 분산 |
| APM (개발) | py-spy / django-silk | django-debug-toolbar | 설치 간단, Django 생태계 표준 |
| APM (운영) | Sentry APM / New Relic | New Relic (선택사항) | 무료 티어 존재, 운영 환경 심층 프로파일링 |
| Load Balancer | HAProxy / AWS ALB | Nginx | 기존 인프라 활용, 추가 비용 없음 |

### 8.3 Infrastructure Reuse

기존 구성 요소를 최대한 재사용하여 추가 인프라 비용을 최소화한다:

```
재사용 인프라:
├── Redis          → View-level caching, Celery broker
├── Celery         → 비동기 작업, Celery Exporter 추가
├── Nginx          → Canary 라우팅, upstream health check
├── Docker Compose → Prometheus, Grafana 서비스 추가
└── PostgreSQL     → pg_stat_statements 활성화
```

---

## 9. Convention Prerequisites

### 9.1 Existing Project Conventions

- [x] `CLAUDE.md` 코딩 컨벤션 존재
- [x] `docs/01-plan/` 구조 확립
- [x] Django 앱 레이어 구조 확립 (`apps/accounts`, `apps/business114` 등)
- [x] 환경변수 관리 (`dongta-django/config/settings/`)
- [x] 테스트 스위트 존재 (`test_danal_payment.py` 등)

### 9.2 환경변수 추가 필요 항목

| Variable | Purpose | Scope | To Be Created |
|----------|---------|-------|:-------------:|
| `PROMETHEUS_METRICS_EXPORT_PORT` | Prometheus scrape 포트 | Server | X |
| `CACHE_MIDDLEWARE_SECONDS` | View cache TTL (초) | Server | X |
| `CACHE_MIDDLEWARE_KEY_PREFIX` | Cache key prefix | Server | X |
| `GRAFANA_ADMIN_PASSWORD` | Grafana 관리자 비밀번호 | Server | X |
| `NEWRELIC_LICENSE_KEY` | New Relic APM 키 (선택) | Server | X |
| `SLOW_QUERY_THRESHOLD_MS` | Slow query 임계값 (ms) | Server | X |

---

## 10. MoSCoW Prioritization

| Priority | 항목 | 이유 |
|----------|------|------|
| Must | FR-01: View-level caching | 목록 API 응답시간 직접 영향 |
| Must | FR-02: Prometheus metrics | 모니터링 기반 없이 운영 불가 |
| Must | FR-03: Grafana dashboard | 운영팀 가시성 확보 필수 |
| Must | FR-04: Canary deployment | 배포 리스크 최소화 필수 |
| Must | FR-05: Slow query optimization | 응답시간 SLA 달성 필수 |
| Should | FR-06: APM 통합 | 심층 프로파일링 도움이 되나 즉각 필수는 아님 |
| Should | FR-07: Nginx health check | 안정성 강화, 설정 간단 |
| Should | FR-08: Cache hit rate 모니터링 | 캐싱 효과 검증에 필요 |
| Could | FR-09: Celery exporter | 부가적 가시성, 우선순위 낮음 |
| Could | FR-10: Blue-Green 자동화 스크립트 | Canary로 충분, 자동화는 추후 |
| Won't | 마이크로서비스 분해 | 현 규모에서 불필요, Phase 6 검토 |
| Won't | CDN 도입 | 별도 Phase로 분리 |

---

## 11. Next Steps

1. [ ] Design 문서 작성 (`Phase_5_배포후_성능_최적화.design.md`) — 아키텍처 다이어그램, API 변경사항, 인프라 설정 세부 사항 포함
2. [ ] CTO 승인 및 스프린트 계획 수립
3. [ ] Staging 환경 준비 (Week 1 시작 전)
4. [ ] 모니터링 기준선(Baseline) 수립 — 최적화 전 현재 응답시간/쿼리 시간 기록

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-09 | Initial draft — Phase 5 Production Hardening 계획 | Product Manager |
