# PHP ↔ Django API 하이브리드 연동 Phase 2.1 Planning Document

> **Summary**: Phase 1 Django API(91% Match Rate) 완성 기반 위에 PHP 레거시와 Django를 무중단으로 연결하는 API 프록시, 인증 통합, 이벤트 로깅, 모니터링 레이어 구축
>
> **Project**: dongta.com
> **Phase**: Phase 2.1 (PHP↔Django 하이브리드 연동 세부 구현)
> **Predecessor**: Phase 1 — Django API 기반 구축 (91% Match Rate 달성)
> **Successor**: Phase 2.2 — 데이터 동기화 파이프라인 / Phase 3 — 모듈별 완전 전환
> **Version**: 1.0.0
> **Author**: PM Agent
> **Date**: 2026-03-17
> **Status**: Draft

---

## Executive Summary

| Perspective | Content |
|-------------|---------|
| **Problem** | Phase 1 Django API가 완성됐으나 기존 PHP 시스템과 분리된 채 운영되어, 실사용자 트래픽이 Django API로 유입되지 않고 PHP 레거시만 사용되는 상태 |
| **Solution** | Nginx API 프록시 라우팅 + PHP 세션-Django JWT 브리지 인증 + 양방향 이벤트 로깅으로 두 시스템을 점진적으로 연결 |
| **Function/UX Effect** | 사용자 세션 단절 없이 PHP↔Django 요청이 투명하게 라우팅되고, 인증 토큰이 자동 발급·갱신되며, 관리자는 실시간 동기화 대시보드로 현황 파악 가능 |
| **Core Value** | 기존 PHP 서비스 무중단 보장 + Django API 점진적 트래픽 이전 + 운영 가시성 확보로 Phase 3 모듈별 전환의 안전한 토대 마련 |

---

## 1. Overview

### 1.1 Purpose

Phase 1에서 구축된 Django REST API(91% Match Rate)를 실 운영 환경에서 PHP 레거시와 안전하게 연결한다. 이를 위해:

1. **API 라우팅 레이어**: Nginx를 통해 `/api/v1/*` 요청을 Django로, 나머지를 PHP Apache로 투명하게 분기
2. **인증 브리지**: 기존 PHP 세션 쿠키 사용자가 Django JWT 없이도 API에 접근할 수 있도록 세션-JWT 변환 레이어 구현
3. **이벤트 로깅**: 양쪽 시스템에서 발생하는 트랜잭션을 공통 이벤트 로그로 추적하여 향후 데이터 동기화(Phase 2.2) 기반 마련
4. **모니터링**: 라우팅 현황, 인증 성공률, 동기화 대기 이벤트 수를 실시간으로 시각화

### 1.2 Background

**Phase 1 성과 (완료)**:
- Django API 91% Match Rate 달성
- 핵심 앱 구현: accounts, business114, recruit, mypage, payment(Danal)
- Docker Compose 운영 환경 구축 (web, db, redis, celery-sync, celery-payment, celery-beat)
- 도메인: dongta.theuit.info (Cloudflare SSL), API: https://dongta.theuit.info/api/v1/

**현재 문제**:
- Django API가 독립 실행 중이나 PHP 시스템과 연결 없음
- 기존 사용자는 PHP 세션 기반 인증만 사용 (Django JWT 미발급 상태)
- 두 시스템 간 데이터 변경 이벤트가 추적되지 않아 향후 동기화 불가
- 운영팀이 두 시스템의 상태를 별도로 모니터링해야 하는 번거로움

**전략적 맥락**:
- 본 Phase 2.1은 Phase 2 하이브리드 연동 계획(아카이브: `docs/archive/2026-03/하이브리드_연동/`)의 세부 구현 단계
- 기존 아카이브된 Phase 2 계획에서 2-1(Nginx) + 2-2(데이터 동기화) 중 인증 통합과 이벤트 로깅을 별도 세분화

### 1.3 Related Documents

- Phase 1 완료 보고서: `docs/04-report/features/마이그레이션.report.md`
- 하이브리드 연동 아카이브: `docs/archive/2026-03/하이브리드_연동/`
- 마이그레이션 전체 계획: `docs/01-plan/features/마이그레이션.plan.md`
- Django API 엔드포인트: https://dongta.theuit.info/api/v1/

---

## 2. Scope

### 2.1 In Scope

**P1 — API 라우팅 (Nginx 설정)**
- [x] 기존 Nginx 리버스 프록시 확인 (Phase 2-1 아카이브 기준 93% 완료)
- [ ] API 버전 라우팅 규칙 정비: `/api/v1/*` → Django, `/api/v2/*` 경로 예약
- [ ] PHP 레거시 `/api/*` 경로 충돌 방지 (기존 PHP API 경로 매핑 조사)
- [ ] 요청/응답 헤더 표준화 (X-Request-ID, X-Forwarded-For)
- [ ] 타임아웃 및 재시도 정책 설정

**P1 — 인증 통합 (세션 ↔ JWT 브리지)**
- [ ] PHP 세션 쿠키 파싱 미들웨어 구현 (Django middleware)
- [ ] PHP 세션 ID → MySQL 세션 조회 → Django User 매핑
- [ ] JWT 자동 발급 엔드포인트: `POST /api/v1/auth/bridge/` (PHP 세션 → JWT)
- [ ] JWT Refresh Token 관리 (Redis 기반)
- [ ] 양측 로그아웃 동기화 (PHP 세션 만료 시 JWT 폐기)
- [ ] 비밀번호 해시 호환성: PHP md5 → Django bcrypt 점진적 업그레이드

**P2 — 이벤트 로깅 (양방향 트랜잭션 추적)**
- [ ] 공통 이벤트 스키마 정의: `SyncEvent` 모델 (event_type, source, entity_type, entity_id, payload, status)
- [ ] PHP 사이드 이벤트 발행: MySQL 트리거 또는 PHP 훅으로 `TBL_EVENT_LOG` 기록
- [ ] Django 사이드 이벤트 발행: Django Signal 기반 `EventOutbox` 기록
- [ ] 이벤트 소비자(Celery Task): 이벤트 로그 → 향후 동기화 파이프라인 연결 준비
- [ ] 트랜잭션 ID(correlation_id) 전파: 요청 추적 가능하도록 헤더 전파

**P2 — 모니터링 대시보드**
- [ ] 라우팅 현황 API: `GET /api/v1/monitoring/routing/` (PHP 요청 수 vs Django 요청 수)
- [ ] 인증 브리지 현황: 세션-JWT 변환 성공률, 실패 원인 분류
- [ ] 이벤트 로그 현황: 대기 중 이벤트 수, 실패 이벤트 DLQ 현황
- [ ] 에러 추적: `GET /api/v1/monitoring/errors/` (최근 에러 목록 + 재시도)
- [ ] Django Admin 기반 운영 화면 (비개발자용)

### 2.2 Out of Scope

- 실제 데이터 동기화 파이프라인 구현 (Phase 2.2 — MySQL↔PostgreSQL 실시간 동기화)
- 모듈별 PHP → Django 완전 전환 (Phase 3)
- 프론트엔드 변경 (기존 PHP 화면 그대로 유지)
- 결제 시스템 Django 완전 이전 (다날 결제 통합 Phase별 진행)
- Prometheus/Grafana 풀스택 모니터링 (Phase 5 성능 최적화 시 도입)
- 신규 기능 개발 (기존 기능 연동에 집중)

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | User Story | Priority | Status |
|----|------------|----------|--------|
| FR-01 | **As a** PHP 프론트엔드 개발자, **I want** `/api/v1/*` 요청이 Django로 자동 라우팅되길 원하며, **So that** 코드 변경 없이 신규 Django API를 사용할 수 있다 | Must | Pending |
| FR-02 | **As a** 로그인한 PHP 세션 사용자, **I want** Django API 호출 시 재로그인 없이 JWT가 자동 발급되길 원하며, **So that** 인증 단절 없이 서비스를 이용할 수 있다 | Must | Pending |
| FR-03 | **As a** 운영자, **I want** PHP 세션과 Django JWT가 동시에 유효하게 관리되길 원하며, **So that** 하이브리드 운영 기간 중 사용자 세션 오류를 방지할 수 있다 | Must | Pending |
| FR-04 | **As a** 개발자, **I want** PHP에서 발생한 회원/주문 이벤트가 `TBL_EVENT_LOG`에 기록되길 원하며, **So that** 향후 PostgreSQL 동기화 파이프라인 구축 시 데이터를 소급 처리할 수 있다 | Should | Pending |
| FR-05 | **As a** Django 개발자, **I want** Django에서 발생한 이벤트가 `EventOutbox`에 기록되길 원하며, **So that** MySQL과의 데이터 정합성을 보장할 수 있다 | Should | Pending |
| FR-06 | **As a** 운영팀, **I want** 실시간 라우팅/인증/이벤트 현황 대시보드를 볼 수 있길 원하며, **So that** 두 시스템의 통합 상태를 단일 화면에서 파악할 수 있다 | Should | Pending |
| FR-07 | **As a** 운영자, **I want** 실패한 이벤트를 재시도할 수 있길 원하며, **So that** 일시적 오류로 인한 데이터 누락을 복구할 수 있다 | Should | Pending |
| FR-08 | **As a** 보안팀, **I want** PHP md5 패스워드 사용자가 Django API 로그인 시 bcrypt로 자동 업그레이드되길 원하며, **So that** 단계적 보안 강화가 가능하다 | Should | Pending |
| FR-09 | **As a** 개발자, **I want** API 요청에 correlation_id가 자동 전파되길 원하며, **So that** PHP와 Django 로그를 단일 요청으로 추적할 수 있다 | Could | Pending |
| FR-10 | **As a** 운영자, **I want** `/api/v2/*` 경로를 예약할 수 있길 원하며, **So that** 향후 API 버전 업그레이드 시 기존 클라이언트 영향 없이 배포할 수 있다 | Could | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Performance | API 라우팅 오버헤드 < 10ms 추가 | k6 부하 테스트 (before/after) |
| Performance | 세션-JWT 브리지 응답 < 100ms | Django Debug Toolbar + 로그 |
| Security | PHP 세션 쿠키 검증 실패 시 401 반환 (세션 위조 방지) | 보안 테스트 |
| Security | JWT 토큰 만료 15분, Refresh 7일 | 코드 리뷰 |
| Reliability | 이벤트 로그 누락 0건 (At-least-once 보장) | 트랜잭션 로깅 검증 |
| Availability | PHP 시스템 장애 시 Django API 독립 운영 가능 | 장애 시뮬레이션 테스트 |
| Compatibility | 기존 PHP 클라이언트 API 경로 100% 호환 | 회귀 테스트 |
| Observability | 라우팅 현황 5초 이내 대시보드 갱신 | 수동 확인 |

---

## 4. User Stories (상세)

### Story 1: API 프록시 라우팅

```
As a PHP 프론트엔드 개발자
I want /api/v1/* 요청이 코드 변경 없이 Django로 라우팅되길 원하고
I want 기존 PHP 페이지 (/*.phtml) 요청은 그대로 PHP로 처리되길 원하며
So that 점진적 마이그레이션 중 두 시스템이 공존할 수 있다

Acceptance Criteria:
- [ ] GET /api/v1/health/ → Django 200 응답 확인
- [ ] GET /login.phtml → PHP Apache 200 응답 확인
- [ ] POST /api/v1/auth/login/ 에 PHP 세션 쿠키 포함 요청 시 JWT 반환
- [ ] /api/v2/* 경로는 503(Service Unavailable) 또는 404 반환 (예약 상태)
- [ ] X-Request-ID 헤더가 PHP → Nginx → Django 전체 경로에 전파됨
```

### Story 2: 세션-JWT 브리지 인증

```
As a 기존 PHP 세션으로 로그인된 사용자
I want Django API 호출 시 재로그인 없이 서비스를 이용하길 원하며
So that 하이브리드 전환 기간 중 사용자 경험이 끊기지 않는다

Acceptance Criteria:
- [ ] PHP 세션 쿠키(PHPSESSID)를 포함한 요청에서 Django JWT 자동 발급 (POST /api/v1/auth/bridge/)
- [ ] 발급된 JWT로 보호된 API 엔드포인트 접근 성공
- [ ] PHP 세션 만료/로그아웃 시 대응 JWT도 Redis에서 블랙리스트 처리
- [ ] 잘못된 세션 쿠키 요청 시 401 Unauthorized 반환
- [ ] md5 패스워드 사용자가 Django 직접 로그인 성공 시 bcrypt로 자동 업그레이드
```

### Story 3: 이벤트 로깅

```
As a 개발자
I want PHP와 Django 양측에서 발생한 중요 이벤트(회원가입, 수정, 결제)가 기록되길 원하며
So that 향후 데이터 동기화 파이프라인(Phase 2.2) 구축 시 이벤트를 소급 처리할 수 있다

Acceptance Criteria:
- [ ] 회원 정보 변경(MySQL TBL_MEMB) 시 TBL_EVENT_LOG에 레코드 자동 생성 (MySQL 트리거)
- [ ] Django accounts 앱 사용자 변경 시 EventOutbox에 레코드 생성 (Django Signal)
- [ ] 이벤트 레코드: event_type, source('php'|'django'), entity_type, entity_id, payload(JSON), status, created_at 포함
- [ ] Celery 워커가 대기 중 이벤트를 5분마다 폴링하여 처리 상태 업데이트
- [ ] 3회 재시도 실패 이벤트는 DLQ(Dead Letter Queue)로 이동
```

### Story 4: 모니터링 대시보드

```
As a 운영팀
I want 두 시스템의 통합 현황을 단일 화면에서 볼 수 있길 원하며
So that 문제 발생 시 빠르게 감지하고 대응할 수 있다

Acceptance Criteria:
- [ ] GET /api/v1/monitoring/status/ → 전체 시스템 현황(라우팅, 인증, 이벤트) JSON 반환
- [ ] GET /api/v1/monitoring/routing/ → PHP vs Django 요청 수 통계 (24시간)
- [ ] GET /api/v1/monitoring/auth/ → 세션-JWT 브리지 성공률, 실패 원인 분류
- [ ] GET /api/v1/monitoring/events/ → 이벤트 상태별 카운트 (pending/done/failed/dlq)
- [ ] POST /api/v1/monitoring/events/{id}/retry/ → 실패 이벤트 수동 재시도
- [ ] Django Admin에서 EventOutbox, SyncLog 관리 화면 제공
```

---

## 5. Success Criteria

### 5.1 Definition of Done

**API 라우팅:**
- [ ] Nginx 설정 적용 후 `/api/v1/*` → Django 라우팅 100% 정상 동작
- [ ] `/api/v1/*` 외 경로 PHP 처리 100% 유지
- [ ] 라우팅 오버헤드 < 10ms (k6 측정)

**인증 통합:**
- [ ] 세션-JWT 브리지 엔드포인트 구현 및 테스트 통과
- [ ] PHP 세션 유효성 검증 미들웨어 Django 통합
- [ ] JWT 발급/갱신/폐기 전체 플로우 E2E 테스트 통과
- [ ] md5 → bcrypt 자동 업그레이드 로직 구현

**이벤트 로깅:**
- [ ] MySQL 트리거 설치 (회원, 결제 테이블)
- [ ] Django Signal 핸들러 등록
- [ ] Celery 이벤트 소비자 Task 구현
- [ ] 이벤트 누락 0건 검증 (단위 테스트)

**모니터링:**
- [ ] 4개 모니터링 API 엔드포인트 구현
- [ ] Django Admin 이벤트 관리 화면 설정
- [ ] 실패 이벤트 수동 재시도 기능 동작

**전체:**
- [ ] pytest coverage ≥ 80% (신규 코드 기준)
- [ ] 기존 PHP 기능 회귀 테스트 0건 실패
- [ ] 스테이징 환경 72시간 무중단 운영 확인

### 5.2 Quality Criteria

- [ ] Python/Django 신규 코드 pytest coverage ≥ 80%
- [ ] flake8 린트 에러 0건
- [ ] 보안: JWT Secret 환경변수 관리, PHP 세션 위조 방지 검증
- [ ] API 응답 시간 P95 < 200ms (브리지 포함)
- [ ] 이벤트 처리 실패율 < 0.1%

---

## 6. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| PHP 세션 데이터 구조 파악 실패 (암호화/직렬화 방식 미확인) | High | Medium | Phase 시작 전 PHP 세션 파일/Redis 구조 역공학 분석 1일 투자 |
| MySQL 트리거가 PHP 쓰기 성능에 영향 | Medium | Medium | 트리거를 비동기 Queue Insert로 경량화, 부하 테스트로 검증 |
| Django JWT와 PHP 세션 동시 관리로 인한 인증 복잡도 증가 | High | Medium | 세션-JWT 브리지를 별도 미들웨어로 격리, 단위 테스트 필수 |
| 이벤트 로그 폭증 (고트래픽 시) | Medium | Low | 이벤트 필터링 정책 수립 (핵심 엔티티만 추적), Redis TTL 설정 |
| PHP 레거시 코드에 MySQL 트리거 영향 (예기치 않은 부작용) | High | Low | 트리거 설치 전 테스트 환경 검증, 롤백 스크립트 준비 |
| Nginx 설정 변경으로 기존 PHP 서비스 중단 | High | Low | 블루/그린 배포, Nginx reload (무중단) 사용, 스테이징 먼저 검증 |
| md5 패스워드 마이그레이션 중 로그인 오류 | Medium | Low | 로그인 시 md5 검증 성공 후 bcrypt 재해시 (점진적 적용) |

---

## 7. Architecture Considerations

### 7.1 Project Level

| Level | Selected | Rationale |
|-------|:--------:|-----------|
| Starter | ☐ | 해당 없음 |
| Dynamic | ☐ | 해당 없음 |
| Enterprise | ✅ | 운영 중 서비스 무중단 통합, 복잡한 인증 브리지, 이벤트 소싱 패턴 필요 |

### 7.2 System Architecture (Phase 2.1)

```
[Browser / Mobile Client]
        |
        | HTTPS:443
        v
[Nginx Reverse Proxy - dongta.theuit.info]
        |
        |--- /api/v1/* ──────────────────────────► [Gunicorn Workers :8000-8002]
        |    (+ X-Request-ID, X-PHP-Session-ID)          |
        |                                           [Django DRF Apps]
        |                                                 |
        |                                    ┌────────────┴───────────────┐
        |                                    |                            |
        |                             [Session Bridge              [Event Outbox]
        |                              Middleware]                  (Django Signal)
        |                                    |                            |
        |                              [Redis JWT]               [Celery Worker]
        |                                    |                            |
        |                              [PostgreSQL]              [MySQL Event Log]
        |
        |--- /* ──────────────────────────────────► [Apache + PHP Legacy :80]
             (기존 PHP 요청 그대로 처리)                     |
                                                      [MySQL RDS]
                                                       (TBL_EVENT_LOG 트리거)
```

### 7.3 Key Architectural Decisions

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| PHP 세션 저장소 | 파일/Redis/MySQL | 현황 확인 필요 | PHP 세션 저장 방식에 따라 브리지 구현 방식 결정 |
| JWT 저장소 | Redis / DB | Redis | 빠른 폐기(블랙리스트), 이미 Redis 운영 중 |
| 이벤트 로깅 방식 | MySQL 트리거 / PHP 훅 | MySQL 트리거 (우선) | 코드 변경 없이 PHP 레거시 이벤트 감지 가능 |
| 이벤트 소비 방식 | Celery 폴링 / 트리거 | Celery 폴링 (5분) | 이미 Celery 운영 중, 실시간 불필요 (Phase 2.2에서 강화) |
| 모니터링 | Prometheus/Grafana / Django API | Django REST API | 간단한 대시보드로 시작, 별도 인프라 불필요 |
| API 버전 관리 | URL 버전 / 헤더 버전 | URL 버전 (/api/v1/, /api/v2/) | 기존 설계 일관성, 직관적 |

### 7.4 New Components

| Component | Location | Description |
|-----------|----------|-------------|
| SessionBridgeMiddleware | `apps/accounts/middleware.py` | PHP 세션 쿠키 → Django User 매핑 |
| BridgeAuthView | `apps/accounts/views.py` | POST /api/v1/auth/bridge/ |
| EventOutbox 확장 | `apps/sync/models.py` | Phase 2 기존 모델 활용 + Django Signal 연결 |
| PHP MySQL 트리거 | `scripts/mysql_triggers.sql` | TBL_MEMB, TBL_RECRUIT INSERT/UPDATE |
| MonitoringViewSet | `apps/monitoring/views.py` | 4개 모니터링 엔드포인트 |
| RoutingStatsMiddleware | `apps/monitoring/middleware.py` | 요청 카운터 (Redis) |

---

## 8. Convention Prerequisites

### 8.1 환경 변수 추가 필요

| Variable | Purpose | Scope | Required |
|----------|---------|-------|:--------:|
| `PHP_SESSION_SECRET` | PHP 세션 복호화 키 | Server | ✅ |
| `PHP_SESSION_STORAGE` | 세션 저장소 타입 (file/redis/mysql) | Server | ✅ |
| `PHP_SESSION_REDIS_URL` | PHP Redis URL (세션 저장소가 Redis인 경우) | Server | 조건부 |
| `BRIDGE_JWT_TTL_MINUTES` | 브리지 발급 JWT 만료 시간 (기본 15분) | Server | 선택 |
| `EVENT_LOG_ENABLED` | 이벤트 로깅 활성화 여부 (기본 True) | Server | 선택 |

### 8.2 신규 앱 구조

```
dongta-django/apps/
├── accounts/
│   ├── middleware.py         # SessionBridgeMiddleware (신규)
│   ├── views.py              # BridgeAuthView 추가
│   └── tests/
│       └── test_bridge.py    # 세션-JWT 브리지 테스트
├── sync/                     # Phase 2 기존 앱 확장
│   ├── models.py             # EventOutbox에 Signal 연결
│   └── signals.py            # Django Signal 핸들러 (신규)
└── monitoring/               # 신규 앱
    ├── __init__.py
    ├── apps.py
    ├── middleware.py         # RoutingStatsMiddleware
    ├── views.py              # MonitoringViewSet
    ├── urls.py
    └── tests/
        └── test_monitoring.py
```

---

## 9. Implementation Roadmap

### Sprint 1 (Week 1-2): API 라우팅 + 인증 브리지 기반

```
Day 1-2: PHP 세션 저장소 구조 분석, 환경 변수 확인
Day 3-5: Nginx 설정 정비 (버전 라우팅, X-Request-ID)
Day 6-7: SessionBridgeMiddleware 구현 + 단위 테스트
Day 8-10: BridgeAuthView (POST /api/v1/auth/bridge/) 구현
```

### Sprint 2 (Week 3-4): 이벤트 로깅 + 인증 완성

```
Day 11-12: MySQL 트리거 작성 (TBL_MEMB, TBL_RECRUIT, TBL_PAYMENT)
Day 13-14: Django Signal 핸들러 (accounts, recruit 앱)
Day 15-16: md5 → bcrypt 자동 업그레이드 로직
Day 17-18: JWT 폐기(블랙리스트) + PHP 로그아웃 연동
Day 19-20: 이벤트 Celery Task 연결 + 재시도 로직
```

### Sprint 3 (Week 5-6): 모니터링 + 통합 테스트

```
Day 21-23: monitoring 앱 구현 (4개 API + RoutingStatsMiddleware)
Day 24-25: Django Admin 이벤트 관리 화면
Day 26-27: E2E 통합 테스트 (PHP 세션 → JWT → API 호출 전체 플로우)
Day 28-30: 스테이징 배포 + 72시간 무중단 운영 검증
```

---

## 10. Next Steps

1. [ ] `/pdca design PHP_Django_하이브리드_연동_2.1` — 상세 기술 설계 문서 작성
2. [ ] PHP 세션 저장소 현황 확인 (파일/Redis/MySQL)
3. [ ] MySQL TBL_MEMB, TBL_RECRUIT, TBL_PAYMENT 스키마 확인 (트리거 대상 컬럼 파악)
4. [ ] 기존 Nginx 설정 현황 검토 (`config/nginx/` 디렉터리)
5. [ ] CTO 검토 및 Sprint 1 착수 승인

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-03-17 | Phase 2.1 초기 계획 수립 | PM Agent |
