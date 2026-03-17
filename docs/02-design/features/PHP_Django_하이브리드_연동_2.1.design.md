# PHP <> Django 하이브리드 연동 Phase 2.1 Design Document

> **Summary**: Nginx API 프록시 라우팅 + PHP 세션-JWT 브리지 인증 + 양방향 이벤트 로깅 + 모니터링 API를 통한 PHP/Django 무중단 하이브리드 연동 상세 설계
>
> **Project**: dongta.com
> **Version**: 1.0.0
> **Author**: Team
> **Date**: 2026-03-17
> **Status**: Draft
> **Planning Doc**: [PHP_Django_하이브리드_연동_2.1.plan.md](../../01-plan/features/PHP_Django_하이브리드_연동_2.1.plan.md)

### Pipeline References

| Phase | Document | Status |
|-------|----------|--------|
| Phase 1 | [마이그레이션 완료 보고서](../../04-report/features/마이그레이션.report.md) | Approved |
| Phase 2 (Archive) | [하이브리드 연동 설계](../../archive/2026-03/하이브리드_연동/하이브리드_연동.design.md) | Deprecated (본 문서로 대체) |
| Phase 2.1 | 본 문서 (세부 구현 설계) | Draft |

---

## 1. Overview

### 1.1 Design Goals

1. **무중단 API 라우팅**: Nginx를 통해 `/api/v1/*` -> Django, `/*` -> PHP Apache로 투명 분기
2. **인증 브리지**: PHP 세션 쿠키 사용자가 재로그인 없이 Django JWT를 자동 발급받는 미들웨어
3. **이벤트 추적 기반**: 양측 시스템 트랜잭션을 `EventOutbox`로 통합 기록하여 Phase 2.2 동기화 파이프라인 토대 마련
4. **운영 가시성**: 모니터링 REST API로 라우팅/인증/이벤트 현황 실시간 제공

### 1.2 Design Principles

- **격리(Isolation)**: 세션 브리지와 이벤트 로깅은 기존 인증/비즈니스 로직에 영향을 주지 않는 별도 레이어로 구현
- **무해(Harmless)**: PHP 레거시 코드 변경 최소화 (MySQL 트리거만 추가, PHP 코드 수정 없음)
- **점진적(Incremental)**: 각 Step을 독립 배포 가능하게 설계하여 문제 발생 시 즉시 롤백
- **관찰 가능(Observable)**: 모든 브리지/이벤트 처리에 correlation_id 전파

---

## 2. Architecture

### 2.1 시스템 아키텍처 다이어그램

```
                            [Browser / Mobile Client]
                                      |
                                      | HTTPS:443 (Cloudflare SSL)
                                      v
                    +--------------------------------------+
                    |   Nginx Reverse Proxy                |
                    |   dongta.theuit.info:443             |
                    |                                      |
                    |   +-- X-Request-ID 생성 -----------+ |
                    |   +-- X-Forwarded-For 추가 --------+ |
                    +------+-------------------+-----------+
                           |                   |
              /api/v1/*    |                   |    /* (나머지 전체)
                           v                   v
            +-----------------------------+  +-------------------------+
            |  Docker: web (Gunicorn)     |  |  Docker: Apache + PHP   |
            |  127.0.0.1:8000             |  |  127.0.0.1:3000         |
            |                             |  |                         |
            |  +-- RequestIDMiddleware    |  |  [PHP Legacy App]       |
            |  +-- RoutingStatsMiddleware |  |    |                    |
            |  +-- SessionBridgeMiddleware|  |    v                    |
            |  +-- JWTAuthentication      |  |  +-------------------+  |
            |                             |  |  | MySQL (Legacy)    |  |
            |  [Django DRF Apps]          |  |  | TBL_MEMB          |  |
            |   accounts/  business114/   |  |  | TBL_RECRUIT       |  |
            |   recruit/   payment/       |  |  | TBL_PAYMENT       |  |
            |   board/     mypage/        |  |  | TBL_EVENT_OUTBOX  |  |
            |   sync/      monitoring/    |  |  | (MySQL Triggers)  |  |
            +-------+----------+----------+  +----------+----------+--+
                    |          |                         |
                    v          v                         |
            +----------+ +-----------+                   |
            |PostgreSQL| |  Redis    |                   |
            |(Django)  | | JWT Cache |                   |
            |          | | Stats     |                   |
            |          | | Celery    |                   |
            +----------+ +-----+-----+                  |
                               |                         |
                    +----------v-----------+             |
                    | Celery Workers        |             |
                    |  celery-sync:         |<--- 5min ---+
                    |   EventOutbox polling |  (MySQL TBL_EVENT_OUTBOX)
                    |  celery-payment:      |
                    |   결제 처리           |
                    |  celery-beat:         |
                    |   스케줄러            |
                    +-----------------------+
```

### 2.2 인증 브리지 시퀀스 다이어그램

```
Browser           Nginx            Django                Redis         MySQL(Legacy)
  |                 |                 |                     |               |
  |-- GET /api/v1/recruit/ --------->|                     |               |
  |  (Cookie: PHPSESSID=abc123)      |                     |               |
  |                 |                 |                     |               |
  |                 |  proxy_pass     |                     |               |
  |                 |  +X-Request-ID  |                     |               |
  |                 |  +X-PHP-Session |                     |               |
  |                 |---------------->|                     |               |
  |                 |                 |                     |               |
  |                 |                 |-- [SessionBridgeMiddleware] ------->|
  |                 |                 |   1. PHPSESSID 추출                 |
  |                 |                 |   2. Redis 캐시 조회 ->|            |
  |                 |                 |      (캐시 HIT: 바로 JWT 매핑)     |
  |                 |                 |      (캐시 MISS:)      |            |
  |                 |                 |   3. MySQL sessions 조회 ---------> |
  |                 |                 |      SELECT * FROM TBL_MEMB        |
  |                 |                 |      WHERE NO_MEMB = {session_uid} |
  |                 |                 |   <---------------------------------|
  |                 |                 |   4. Member 매핑 (username 기준)    |
  |                 |                 |   5. JWT 생성 & Redis 저장          |
  |                 |                 |   ----------------->|               |
  |                 |                 |                     |               |
  |                 |                 |-- [DRF View 처리]   |               |
  |                 |                 |                     |               |
  |                 |<----------------|                     |               |
  |<----------------|                 |                     |               |
  |  (Authorization: Bearer {jwt})    |                     |               |
  |  (Set-Cookie: dongta_jwt=...)     |                     |               |
```

### 2.3 이벤트 로깅 플로우

```
[PHP Side]                              [Django Side]
     |                                       |
 TBL_MEMB UPDATE                      accounts.Member.save()
     |                                       |
     v                                       v
 MySQL Trigger                         Django Signal
 tg_member_update                      post_save -> handle_member_change
     |                                       |
     v                                       v
 TBL_EVENT_OUTBOX (MySQL)             sync_event_outbox (PostgreSQL)
 {source: 'php',                      {source: 'django',
  event_type: 'member.update',         event_type: 'member.update',
  aggregate_id: NO_MEMB,               aggregate_id: member.pk,
  payload: {...},                       payload: {...},
  status: 'pending'}                    status: 'pending'}
     |                                       |
     +--------------- Celery ----------------+
                       |
              5분 간격 폴링
                       |
              +--------v--------+
              | process_events  |
              | - MySQL 이벤트: |
              |   PostgreSQL 반영|
              | - Django 이벤트:|
              |   로그만 기록    |
              |   (Phase 2.2에서 |
              |    MySQL 역동기화)|
              +-----------------+
```

### 2.4 Dependencies

| Component | Depends On | Purpose |
|-----------|-----------|---------|
| SessionBridgeMiddleware | MySQL `legacy` DB, Redis | PHP 세션 조회 & JWT 캐시 |
| RoutingStatsMiddleware | Redis | 요청 카운터 저장 |
| MonitoringViewSet | Redis, PostgreSQL | 통계 집계 |
| Django Signal Handlers | EventOutbox (PostgreSQL) | 이벤트 기록 |
| Celery Event Processor | MySQL `legacy` DB, PostgreSQL | 이벤트 소비 |
| MySQL Triggers | TBL_EVENT_OUTBOX (MySQL) | PHP 이벤트 감지 |

---

## 3. Data Model

### 3.1 MySQL: TBL_EVENT_OUTBOX (PHP 사이드)

기존 아카이브 설계의 `TBL_EVENT_OUTBOX`를 `source` 컬럼과 `correlation_id`로 확장한다.

```sql
CREATE TABLE IF NOT EXISTS TBL_EVENT_OUTBOX (
    event_id        BIGINT PRIMARY KEY AUTO_INCREMENT,
    source          VARCHAR(10) NOT NULL DEFAULT 'php'
                    COMMENT 'php | django',
    event_type      VARCHAR(50) NOT NULL
                    COMMENT 'member.insert | member.update | recruit.insert | ...',
    aggregate_type  VARCHAR(50) NOT NULL
                    COMMENT 'member | recruit | payment | business',
    aggregate_id    BIGINT NOT NULL
                    COMMENT '원본 테이블 PK (예: NO_MEMB)',
    payload         JSON NOT NULL
                    COMMENT '변경 데이터 (JSON)',
    correlation_id  VARCHAR(64) NULL
                    COMMENT 'X-Request-ID (요청 추적)',
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    COMMENT 'pending | processing | done | failed | dead_letter',
    retry_count     SMALLINT NOT NULL DEFAULT 0,
    max_retries     SMALLINT NOT NULL DEFAULT 3,
    error_message   TEXT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at    TIMESTAMP NULL,

    INDEX idx_outbox_status_created (status, created_at),
    INDEX idx_outbox_aggregate (aggregate_type, aggregate_id),
    INDEX idx_outbox_correlation (correlation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='PHP/Django 이벤트 아웃박스 (하이브리드 연동)';
```

### 3.2 MySQL Triggers

#### 3.2.1 회원 테이블 트리거

```sql
DELIMITER //

CREATE TRIGGER tg_memb_after_insert
AFTER INSERT ON TBL_MEMB
FOR EACH ROW
BEGIN
    INSERT INTO TBL_EVENT_OUTBOX
        (source, event_type, aggregate_type, aggregate_id, payload)
    VALUES (
        'php',
        'member.insert',
        'member',
        NEW.NO_MEMB,
        JSON_OBJECT(
            'no_memb',    NEW.NO_MEMB,
            'id_member',  NEW.ID_MEMBER,
            'nm_member',  NEW.NM_MEMBER,
            'email',      IFNULL(NEW.EMAIL, ''),
            'phone',      IFNULL(NEW.TEL, ''),
            'memb_level', NEW.MEMB_LEVEL,
            'reg_date',   NEW.REG_DATE
        )
    );
END //

CREATE TRIGGER tg_memb_after_update
AFTER UPDATE ON TBL_MEMB
FOR EACH ROW
BEGIN
    -- 실제 변경이 있을 때만 이벤트 발행 (불필요한 이벤트 방지)
    IF OLD.NM_MEMBER != NEW.NM_MEMBER
       OR OLD.EMAIL != NEW.EMAIL
       OR OLD.TEL != NEW.TEL
       OR OLD.MEMB_LEVEL != NEW.MEMB_LEVEL
       OR OLD.DL_GB != NEW.DL_GB
    THEN
        INSERT INTO TBL_EVENT_OUTBOX
            (source, event_type, aggregate_type, aggregate_id, payload)
        VALUES (
            'php',
            'member.update',
            'member',
            NEW.NO_MEMB,
            JSON_OBJECT(
                'no_memb',    NEW.NO_MEMB,
                'id_member',  NEW.ID_MEMBER,
                'nm_member',  NEW.NM_MEMBER,
                'email',      IFNULL(NEW.EMAIL, ''),
                'phone',      IFNULL(NEW.TEL, ''),
                'memb_level', NEW.MEMB_LEVEL,
                'dl_gb',      NEW.DL_GB,
                'old_values',  JSON_OBJECT(
                    'nm_member',  OLD.NM_MEMBER,
                    'email',      IFNULL(OLD.EMAIL, ''),
                    'phone',      IFNULL(OLD.TEL, ''),
                    'memb_level', OLD.MEMB_LEVEL,
                    'dl_gb',      OLD.DL_GB
                )
            )
        );
    END IF;
END //

DELIMITER ;
```

#### 3.2.2 채용공고 테이블 트리거

```sql
DELIMITER //

CREATE TRIGGER tg_recruit_after_insert
AFTER INSERT ON TBL_RECRUIT
FOR EACH ROW
BEGIN
    INSERT INTO TBL_EVENT_OUTBOX
        (source, event_type, aggregate_type, aggregate_id, payload)
    VALUES (
        'php',
        'recruit.insert',
        'recruit',
        NEW.NO_RECRUIT,
        JSON_OBJECT(
            'no_recruit',  NEW.NO_RECRUIT,
            'no_memb',     NEW.NO_MEMB,
            'title',       NEW.TITLE,
            'reg_date',    NEW.REG_DATE
        )
    );
END //

CREATE TRIGGER tg_recruit_after_update
AFTER UPDATE ON TBL_RECRUIT
FOR EACH ROW
BEGIN
    INSERT INTO TBL_EVENT_OUTBOX
        (source, event_type, aggregate_type, aggregate_id, payload)
    VALUES (
        'php',
        'recruit.update',
        'recruit',
        NEW.NO_RECRUIT,
        JSON_OBJECT(
            'no_recruit', NEW.NO_RECRUIT,
            'no_memb',    NEW.NO_MEMB,
            'title',      NEW.TITLE,
            'dl_gb',      NEW.DL_GB
        )
    );
END //

DELIMITER ;
```

### 3.3 PostgreSQL: EventOutbox 확장

기존 `apps/sync/models.py`의 `EventOutbox` 모델에 `source`와 `correlation_id` 필드를 추가한다.

```python
# apps/sync/models.py (기존 모델 확장)

class EventSource(models.TextChoices):
    PHP = 'php', 'PHP Legacy'
    DJANGO = 'django', 'Django'


class EventOutbox(models.Model):
    # ... 기존 필드 유지 ...

    # Phase 2.1 추가 필드
    source = models.CharField(
        max_length=10,
        choices=EventSource.choices,
        default=EventSource.DJANGO,
        verbose_name='이벤트 소스',
        db_index=True,
    )
    correlation_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='요청 추적 ID',
        help_text='X-Request-ID 헤더 값',
        db_index=True,
    )
```

**마이그레이션 SQL (자동 생성 예상)**:
```sql
ALTER TABLE sync_event_outbox
    ADD COLUMN source VARCHAR(10) NOT NULL DEFAULT 'django',
    ADD COLUMN correlation_id VARCHAR(64) NOT NULL DEFAULT '',
    ADD INDEX idx_outbox_source (source),
    ADD INDEX idx_outbox_correlation (correlation_id);
```

### 3.4 PostgreSQL: 모니터링 통계 (Redis 기반, DB 저장 없음)

라우팅 통계와 인증 통계는 Redis에만 저장한다. 별도 DB 테이블 불필요.

**Redis Key 설계**:

| Key Pattern | Type | TTL | Description |
|-------------|------|-----|-------------|
| `routing:django:{YYYYMMDD}:{HH}` | HASH | 48h | 시간별 Django 요청 수 (method별) |
| `routing:php:{YYYYMMDD}:{HH}` | HASH | 48h | 시간별 PHP 요청 수 |
| `auth:bridge:success:{YYYYMMDD}` | INT | 48h | 일별 브리지 성공 수 |
| `auth:bridge:fail:{YYYYMMDD}:{reason}` | INT | 48h | 일별 브리지 실패 수 (사유별) |
| `session:bridge:{PHPSESSID}` | JSON | 15min | 세션-JWT 매핑 캐시 |
| `jwt:blacklist:{jti}` | STRING | JWT TTL | 폐기된 JWT |

### 3.5 Entity Relationships

```
[PHP MySQL]                          [Django PostgreSQL]
TBL_MEMB -----(trigger)----> TBL_EVENT_OUTBOX
  |                               |
  |  (Celery polling)             |
  |                               v
  +--- username 기준 매핑 ---> accounts_member
                                  |
                            (Django Signal)
                                  |
                                  v
                           sync_event_outbox
                                  |
                            (Celery polling)
                                  |
                                  v
                           sync_log (이력)
```

---

## 4. API Specification

### 4.1 Endpoint List

| Method | Path | Description | Auth | Priority |
|--------|------|-------------|------|----------|
| POST | `/api/v1/auth/bridge/` | PHP 세션 -> JWT 발급 | PHP Session | P1 |
| POST | `/api/v1/auth/bridge/refresh/` | 브리지 JWT 갱신 | Bearer JWT | P1 |
| POST | `/api/v1/auth/bridge/revoke/` | 브리지 JWT 폐기 (로그아웃 연동) | Bearer JWT | P1 |
| GET | `/api/v1/monitoring/status/` | 전체 시스템 현황 | Admin JWT | P2 |
| GET | `/api/v1/monitoring/routing/` | PHP vs Django 트래픽 비율 | Admin JWT | P2 |
| GET | `/api/v1/monitoring/auth/` | 인증 브리지 성공률 | Admin JWT | P2 |
| GET | `/api/v1/monitoring/events/` | 이벤트 처리 상태 | Admin JWT | P2 |
| POST | `/api/v1/monitoring/events/{id}/retry/` | 실패 이벤트 수동 재시도 | Admin JWT | P2 |

### 4.2 Detailed Specification

#### 4.2.1 `POST /api/v1/auth/bridge/` -- PHP 세션 -> JWT

PHP 세션 쿠키를 기반으로 Django JWT를 발급한다. 프론트엔드 JavaScript가 명시적으로 호출하거나, `SessionBridgeMiddleware`가 자동으로 처리한다.

**Request:**
```http
POST /api/v1/auth/bridge/ HTTP/1.1
Host: dongta.theuit.info
Cookie: PHPSESSID=abc123def456
Content-Type: application/json
X-Request-ID: req-uuid-001
```

```json
{
    "php_session_id": "abc123def456"
}
```

> `php_session_id`는 선택적이다. Cookie에 `PHPSESSID`가 있으면 자동 추출한다.

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "user": {
            "id": 42,
            "username": "hong_gildong",
            "name": "홍길동",
            "email": "hong@example.com",
            "level": 9,
            "member_type": "individual"
        },
        "bridge_info": {
            "php_session_valid": true,
            "password_upgrade_needed": true,
            "session_expires_at": "2026-03-17T15:30:00+09:00"
        }
    },
    "error": null
}
```

**Error Responses:**

| HTTP Status | Error Code | Message | Cause |
|------------|-----------|---------|-------|
| 401 | `BRIDGE_001` | PHP 세션이 유효하지 않습니다 | PHPSESSID 없음 또는 만료 |
| 401 | `BRIDGE_002` | 세션에 해당하는 회원을 찾을 수 없습니다 | MySQL 회원 조회 실패 |
| 401 | `BRIDGE_003` | Django 회원 매핑에 실패했습니다 | PostgreSQL 회원 미존재 |
| 503 | `BRIDGE_004` | PHP 세션 저장소에 연결할 수 없습니다 | MySQL legacy DB 연결 실패 |
| 429 | `BRIDGE_005` | 브리지 요청 한도를 초과했습니다 | Rate Limit (10/min per IP) |

**Error Response Example (401):**
```json
{
    "success": false,
    "data": null,
    "error": {
        "code": "BRIDGE_001",
        "message": "PHP 세션이 유효하지 않습니다",
        "details": {
            "session_id_present": false,
            "hint": "Cookie에 PHPSESSID가 포함되어 있는지 확인하세요"
        }
    }
}
```

#### 4.2.2 `POST /api/v1/auth/bridge/refresh/` -- 브리지 JWT 갱신

기존 `rest_framework_simplejwt.views.TokenRefreshView`를 그대로 사용한다. 브리지로 발급된 JWT와 직접 로그인으로 발급된 JWT를 구분하지 않는다.

**Request:**
```json
{
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    },
    "error": null
}
```

#### 4.2.3 `POST /api/v1/auth/bridge/revoke/` -- 브리지 JWT 폐기

PHP 로그아웃 시 호출하여 대응 JWT를 블랙리스트에 추가한다.

**Request:**
```json
{
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "php_session_id": "abc123def456"
}
```

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "message": "JWT가 폐기되었습니다",
        "session_cache_cleared": true
    },
    "error": null
}
```

#### 4.2.4 `GET /api/v1/monitoring/status/` -- 전체 현황

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "system": {
            "django": "healthy",
            "postgresql": "healthy",
            "redis": "healthy",
            "mysql_legacy": "healthy",
            "celery_sync": "healthy",
            "celery_payment": "healthy"
        },
        "routing": {
            "today_django_requests": 15234,
            "today_php_requests": 42891,
            "django_ratio": 0.262
        },
        "auth_bridge": {
            "today_success": 1823,
            "today_failures": 12,
            "success_rate": 0.993
        },
        "events": {
            "pending": 5,
            "processing": 2,
            "done_today": 312,
            "failed": 1,
            "dead_letter": 0
        },
        "timestamp": "2026-03-17T14:30:00+09:00"
    },
    "error": null
}
```

#### 4.2.5 `GET /api/v1/monitoring/routing/` -- 라우팅 통계

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `hours` | int | 24 | 조회 기간 (시간) |
| `granularity` | string | `hourly` | `hourly` or `daily` |

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "period": {
            "from": "2026-03-16T14:00:00+09:00",
            "to": "2026-03-17T14:00:00+09:00",
            "granularity": "hourly"
        },
        "summary": {
            "total_requests": 58125,
            "django_requests": 15234,
            "php_requests": 42891,
            "django_ratio": 0.262
        },
        "timeline": [
            {
                "hour": "2026-03-17T13:00:00+09:00",
                "django": 892,
                "php": 2103,
                "django_methods": {"GET": 756, "POST": 120, "PUT": 12, "DELETE": 4}
            }
        ]
    },
    "error": null
}
```

#### 4.2.6 `GET /api/v1/monitoring/auth/` -- 인증 브리지 통계

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "period": "2026-03-17",
        "total_attempts": 1835,
        "success": 1823,
        "failures": 12,
        "success_rate": 0.993,
        "failure_reasons": {
            "session_expired": 7,
            "member_not_found": 3,
            "django_mapping_failed": 2
        },
        "password_upgrades": {
            "md5_to_argon2": 45,
            "pending_md5_users": 128
        }
    },
    "error": null
}
```

#### 4.2.7 `GET /api/v1/monitoring/events/` -- 이벤트 현황

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | string | `all` | `php`, `django`, `all` |
| `status` | string | `all` | `pending`, `done`, `failed`, `dead_letter`, `all` |
| `limit` | int | 50 | 결과 수 제한 |

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "summary": {
            "php_events": {"pending": 3, "processing": 1, "done": 198, "failed": 0, "dead_letter": 0},
            "django_events": {"pending": 2, "processing": 1, "done": 114, "failed": 1, "dead_letter": 0}
        },
        "recent_events": [
            {
                "id": 512,
                "source": "php",
                "event_type": "member.update",
                "aggregate_type": "member",
                "aggregate_id": 1234,
                "status": "done",
                "created_at": "2026-03-17T14:25:00+09:00",
                "processed_at": "2026-03-17T14:25:03+09:00"
            }
        ]
    },
    "error": null
}
```

#### 4.2.8 `POST /api/v1/monitoring/events/{id}/retry/` -- 이벤트 수동 재시도

**Response (200 OK):**
```json
{
    "success": true,
    "data": {
        "event_id": 510,
        "previous_status": "failed",
        "new_status": "pending",
        "retry_count": 2,
        "message": "이벤트가 재시도 대기열에 추가되었습니다"
    },
    "error": null
}
```

**Error (400):**
```json
{
    "success": false,
    "data": null,
    "error": {
        "code": "EVENT_001",
        "message": "재시도할 수 없는 상태입니다",
        "details": {"current_status": "done"}
    }
}
```

---

## 5. Authentication Bridge (상세 구현)

### 5.1 SessionBridgeMiddleware

**위치**: `apps/accounts/middleware.py`

**동작 조건**: 요청에 `PHPSESSID` 쿠키가 있고, `Authorization` 헤더가 없을 때 자동 실행

```python
# apps/accounts/middleware.py

import logging
import uuid
from django.conf import settings
from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)

BRIDGE_CACHE_PREFIX = 'session:bridge:'
BRIDGE_CACHE_TTL = 900  # 15분


class RequestIDMiddleware:
    """
    X-Request-ID 헤더가 없으면 생성하여 전파.
    모든 로그에 correlation_id로 사용.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get('HTTP_X_REQUEST_ID')
        if not request_id:
            request_id = str(uuid.uuid4())
        request.correlation_id = request_id
        response = self.get_response(request)
        response['X-Request-ID'] = request_id
        return response


class SessionBridgeMiddleware:
    """
    PHP PHPSESSID 쿠키 -> Django JWT 자동 매핑.

    동작 플로우:
    1. PHPSESSID 쿠키 확인
    2. Authorization 헤더가 이미 있으면 SKIP
    3. Redis 캐시 조회 (session:bridge:{PHPSESSID})
    4. 캐시 MISS → MySQL legacy DB에서 세션 소유자 조회
    5. Django Member 매핑 (username 기준)
    6. JWT 생성 & Redis 캐시 저장
    7. request.user 설정
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # JWT가 이미 있으면 미들웨어 스킵
        if request.META.get('HTTP_AUTHORIZATION'):
            return self.get_response(request)

        php_session_id = request.COOKIES.get('PHPSESSID')
        if not php_session_id:
            return self.get_response(request)

        try:
            member = self._resolve_member(php_session_id)
            if member:
                # JWT 생성
                refresh = RefreshToken.for_user(member)
                # request에 사용자 설정 (DRF 인증 우회)
                request.META['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'
                request._bridge_jwt = {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
        except Exception:
            logger.exception(
                'SessionBridge failed for PHPSESSID=%s',
                php_session_id[:8] + '...',
            )

        response = self.get_response(request)

        # 응답에 JWT 포함 (클라이언트가 이후 직접 사용)
        if hasattr(request, '_bridge_jwt'):
            response['X-Bridge-Token'] = request._bridge_jwt['access']

        return response

    def _resolve_member(self, php_session_id):
        """PHPSESSID -> Django Member 매핑 (캐시 우선)"""
        from apps.accounts.models import Member

        cache_key = f'{BRIDGE_CACHE_PREFIX}{php_session_id}'
        cached = cache.get(cache_key)
        if cached:
            try:
                return Member.objects.get(pk=cached['member_pk'])
            except Member.DoesNotExist:
                cache.delete(cache_key)

        # MySQL legacy DB 조회
        member_info = self._query_php_session(php_session_id)
        if not member_info:
            return None

        # Django Member 매핑
        try:
            member = Member.objects.get(
                username=member_info['id_member'],
                is_deleted=False,
            )
        except Member.DoesNotExist:
            logger.warning(
                'Bridge: no Django member for PHP user %s',
                member_info['id_member'],
            )
            return None

        # 캐시 저장
        cache.set(cache_key, {'member_pk': member.pk}, BRIDGE_CACHE_TTL)
        return member

    @staticmethod
    def _query_php_session(php_session_id):
        """
        MySQL legacy DB에서 PHP 세션 데이터 조회.

        PHP 세션 저장 방식에 따라 구현이 달라진다:
        - 파일 기반: /tmp/sess_{PHPSESSID} 파일 파싱 (서버 접근 필요)
        - MySQL 기반: sessions 테이블 조회
        - Redis 기반: Redis에서 직접 조회

        아래는 MySQL 기반 세션 조회 예시이다.
        실제 구현 전 PHP 세션 저장소 확인이 필수이다.
        """
        from django.db import connections

        try:
            with connections['legacy'].cursor() as cursor:
                # PHP 세션 테이블 구조에 따라 쿼리 조정 필요
                # 방법 1: PHP가 별도 세션 테이블을 사용하는 경우
                cursor.execute("""
                    SELECT m.NO_MEMB, m.ID_MEMBER, m.NM_MEMBER,
                           m.EMAIL, m.MEMB_LEVEL
                    FROM TBL_SESSION s
                    JOIN TBL_MEMB m ON s.NO_MEMB = m.NO_MEMB
                    WHERE s.SESSION_ID = %s
                      AND s.EXPIRE_AT > NOW()
                      AND m.DL_GB = 'N'
                """, [php_session_id])

                row = cursor.fetchone()
                if row:
                    return {
                        'no_memb': row[0],
                        'id_member': row[1],
                        'nm_member': row[2],
                        'email': row[3],
                        'memb_level': row[4],
                    }
        except Exception:
            logger.exception('Failed to query PHP session from MySQL')

        return None
```

### 5.2 md5 -> Argon2id 자동 패스워드 업그레이드

기존 `apps/accounts/hashers.py`의 `LegacyMD5PasswordHasher`가 이미 구현되어 있다. Django의 `check_password()` 메커니즘에 의해 md5 해시로 인증 성공 시 자동으로 `PASSWORD_HASHERS[0]` (Argon2id)로 재해시된다.

**추가 구현 없이 동작하는 이유**:
- `settings.PASSWORD_HASHERS`에 `LegacyMD5PasswordHasher`가 마지막 항목으로 등록됨
- Django `AbstractBaseUser.check_password()`는 인증 성공 시 현재 해시가 `preferred` 해셔(첫 번째)가 아니면 자동 rehash
- 브리지를 통한 접근에서는 패스워드 체크가 없으므로, `bridge_info.password_upgrade_needed` 플래그로 클라이언트에 알림

### 5.3 BridgeAuthView

**위치**: `apps/accounts/views.py` (기존 파일에 추가)

```python
# apps/accounts/views.py (추가 View)

class BridgeAuthView(generics.GenericAPIView):
    """
    POST /api/v1/auth/bridge/
    PHP 세션 쿠키 -> Django JWT 명시적 발급

    SessionBridgeMiddleware는 자동 처리를 담당하고,
    이 View는 클라이언트가 명시적으로 JWT를 요청할 때 사용한다.
    """
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'bridge'

    def post(self, request):
        php_session_id = (
            request.data.get('php_session_id')
            or request.COOKIES.get('PHPSESSID')
        )

        if not php_session_id:
            return error_response(
                'BRIDGE_001',
                'PHP 세션이 유효하지 않습니다',
                details={'session_id_present': False,
                         'hint': 'Cookie에 PHPSESSID가 포함되어 있는지 확인하세요'},
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        # PHP 세션 -> 회원 정보 조회
        member_info = SessionBridgeMiddleware._query_php_session(php_session_id)
        if not member_info:
            return error_response(
                'BRIDGE_002',
                '세션에 해당하는 회원을 찾을 수 없습니다',
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        # Django Member 매핑
        try:
            member = Member.objects.get(
                username=member_info['id_member'],
                is_deleted=False,
            )
        except Member.DoesNotExist:
            return error_response(
                'BRIDGE_003',
                'Django 회원 매핑에 실패했습니다',
                details={'php_username': member_info['id_member']},
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        # JWT 발급
        refresh = RefreshToken.for_user(member)

        # 패스워드 업그레이드 필요 여부 확인
        password_upgrade_needed = (
            member.password.startswith('md5$')
            if member.password else False
        )

        # 통계 기록 (Redis)
        self._record_bridge_success()

        return success_response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': MemberSerializer(member).data,
            'bridge_info': {
                'php_session_valid': True,
                'password_upgrade_needed': password_upgrade_needed,
            },
        })

    @staticmethod
    def _record_bridge_success():
        from django.core.cache import cache
        from django.utils import timezone
        key = f'auth:bridge:success:{timezone.now().strftime("%Y%m%d")}'
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=172800)  # 48h


class BridgeRevokeView(generics.GenericAPIView):
    """
    POST /api/v1/auth/bridge/revoke/
    PHP 로그아웃 시 대응 JWT 폐기 + 세션 캐시 클리어
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        php_session_id = request.data.get('php_session_id')

        # JWT 블랙리스트
        revoked = False
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
                revoked = True
            except Exception:
                pass

        # 세션 캐시 클리어
        cache_cleared = False
        if php_session_id:
            cache_key = f'session:bridge:{php_session_id}'
            cache.delete(cache_key)
            cache_cleared = True

        return success_response({
            'message': 'JWT가 폐기되었습니다',
            'jwt_revoked': revoked,
            'session_cache_cleared': cache_cleared,
        })
```

### 5.4 URL 설정 (accounts)

`apps/accounts/urls.py`에 추가:

```python
# 기존 urlpatterns에 추가
path('bridge/', views.BridgeAuthView.as_view(), name='auth-bridge'),
path('bridge/refresh/', TokenRefreshView.as_view(), name='auth-bridge-refresh'),
path('bridge/revoke/', views.BridgeRevokeView.as_view(), name='auth-bridge-revoke'),
```

---

## 6. Event Logging (Django Signal)

### 6.1 Signal Handlers

**신규 파일**: `apps/sync/signals.py`

```python
# apps/sync/signals.py

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.accounts.models import Member
from apps.recruit.models import RecruitPosting
from apps.sync.models import EventOutbox, EventType, EventSource

logger = logging.getLogger(__name__)


def _get_correlation_id():
    """현재 요청의 correlation_id를 가져온다 (미들웨어에서 설정)"""
    import threading
    return getattr(threading.current_thread(), 'correlation_id', '')


@receiver(post_save, sender=Member)
def handle_member_save(sender, instance, created, **kwargs):
    """회원 생성/수정 시 EventOutbox에 기록"""
    event_type = EventType.MEMBER_INSERT if created else EventType.MEMBER_UPDATE

    EventOutbox.objects.create(
        source=EventSource.DJANGO,
        event_type=event_type,
        aggregate_type='member',
        aggregate_id=instance.pk,
        correlation_id=_get_correlation_id(),
        payload={
            'pk': instance.pk,
            'username': instance.username,
            'name': instance.name,
            'email': instance.email,
            'phone': instance.phone,
            'level': instance.level,
            'is_active': instance.is_active,
        },
    )
    logger.info(
        '[EVENT] %s member pk=%s username=%s',
        event_type, instance.pk, instance.username,
    )


@receiver(post_save, sender=RecruitPosting)
def handle_recruit_save(sender, instance, created, **kwargs):
    """채용공고 생성/수정 시 EventOutbox에 기록"""
    event_type = EventType.RECRUIT_INSERT if created else EventType.RECRUIT_UPDATE

    EventOutbox.objects.create(
        source=EventSource.DJANGO,
        event_type=event_type,
        aggregate_type='recruit',
        aggregate_id=instance.pk,
        correlation_id=_get_correlation_id(),
        payload={
            'pk': instance.pk,
            'title': getattr(instance, 'title', ''),
        },
    )
```

### 6.2 Signal Registration

**수정**: `apps/sync/apps.py`

```python
# apps/sync/apps.py

from django.apps import AppConfig


class SyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sync'
    verbose_name = '데이터 동기화'

    def ready(self):
        import apps.sync.signals  # noqa: F401
```

### 6.3 Celery Event Processor

**수정**: `apps/sync/tasks.py`에 추가

```python
# apps/sync/tasks.py (추가 Task)

@shared_task(bind=True, max_retries=3, queue='sync')
def process_php_events(self):
    """
    MySQL TBL_EVENT_OUTBOX에서 pending 이벤트를 가져와 PostgreSQL에 반영.
    5분 간격으로 Celery Beat에서 호출.
    """
    from django.db import connections
    from apps.sync.models import EventOutbox, EventStatus, SyncLog
    from django.utils import timezone

    sync_log = SyncLog.objects.create(
        task_id=self.request.id or 'manual',
        result='partial',
    )

    processed = 0
    failed = 0

    try:
        with connections['legacy'].cursor() as cursor:
            cursor.execute("""
                SELECT event_id, source, event_type, aggregate_type,
                       aggregate_id, payload, correlation_id
                FROM TBL_EVENT_OUTBOX
                WHERE status = 'pending'
                  AND source = 'php'
                ORDER BY created_at ASC
                LIMIT %s
            """, [settings.SYNC_BATCH_SIZE])

            rows = cursor.fetchall()

            for row in rows:
                event_id = row[0]
                try:
                    # PostgreSQL에 이벤트 복제
                    EventOutbox.objects.update_or_create(
                        source='php',
                        event_type=row[2],
                        aggregate_id=row[4],
                        defaults={
                            'aggregate_type': row[3],
                            'payload': row[5],
                            'correlation_id': row[6] or '',
                            'status': EventStatus.PENDING,
                        },
                    )

                    # MySQL 이벤트 완료 처리
                    cursor.execute("""
                        UPDATE TBL_EVENT_OUTBOX
                        SET status = 'done', processed_at = NOW()
                        WHERE event_id = %s
                    """, [event_id])

                    processed += 1

                except Exception as e:
                    logger.error('[SYNC] Failed to process PHP event %s: %s', event_id, e)
                    cursor.execute("""
                        UPDATE TBL_EVENT_OUTBOX
                        SET status = 'failed',
                            retry_count = retry_count + 1,
                            error_message = %s
                        WHERE event_id = %s
                    """, [str(e)[:2000], event_id])
                    failed += 1

        # Sync log 업데이트
        sync_log.finished_at = timezone.now()
        sync_log.processed_count = processed
        sync_log.failed_count = failed
        sync_log.result = 'success' if failed == 0 else 'partial'
        sync_log.save()

        return {'processed': processed, 'failed': failed}

    except Exception as e:
        sync_log.result = 'failure'
        sync_log.detail = str(e)
        sync_log.finished_at = timezone.now()
        sync_log.save()
        raise self.retry(exc=e, countdown=60)
```

### 6.4 Celery Beat 추가 설정

`config/settings/base.py`의 `CELERY_BEAT_SCHEDULE`에 추가:

```python
CELERY_BEAT_SCHEDULE = {
    # ... 기존 항목 유지 ...
    'process-php-events-every-5min': {
        'task': 'apps.sync.tasks.process_php_events',
        'schedule': 300,  # 5분
        'options': {'queue': 'sync'},
    },
}
```

---

## 7. Monitoring

### 7.1 신규 앱 구조

```
dongta-django/apps/monitoring/
    __init__.py
    apps.py
    middleware.py    # RoutingStatsMiddleware
    views.py        # MonitoringViewSet
    urls.py
    permissions.py  # AdminOnlyPermission
    tests/
        __init__.py
        test_monitoring.py
```

### 7.2 RoutingStatsMiddleware

**위치**: `apps/monitoring/middleware.py`

```python
# apps/monitoring/middleware.py

from django.core.cache import cache
from django.utils import timezone


class RoutingStatsMiddleware:
    """
    모든 Django 요청을 카운트하여 Redis에 저장.
    Nginx access log 파싱 대신 Django 레벨에서 집계.
    PHP 트래픽은 Nginx access log에서 별도 집계하거나,
    monitoring API에서 총 트래픽 - Django 트래픽으로 추정.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        now = timezone.now()
        date_key = now.strftime('%Y%m%d')
        hour_key = now.strftime('%H')
        method = request.method

        # Redis HASH: routing:django:20260317:14 -> {GET: 100, POST: 20}
        redis_key = f'routing:django:{date_key}:{hour_key}'
        try:
            cache.get_or_set(redis_key, {}, timeout=172800)
            # Atomic increment는 Redis HINCRBY가 필요하므로
            # django.core.cache 대신 직접 Redis 사용 권장
            pipe_key = f'{redis_key}:{method}'
            try:
                cache.incr(pipe_key)
            except ValueError:
                cache.set(pipe_key, 1, timeout=172800)
        except Exception:
            pass  # 통계 실패가 요청을 블로킹하면 안 됨

        return response
```

### 7.3 MonitoringViewSet

**위치**: `apps/monitoring/views.py`

주요 엔드포인트의 구현 골격:

```python
# apps/monitoring/views.py

from rest_framework import views, permissions, status
from django.core.cache import cache
from django.db import connections
from django.utils import timezone
from core.utils import success_response, error_response
from apps.sync.models import EventOutbox, EventStatus, SyncLog


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class SystemStatusView(views.APIView):
    """GET /api/v1/monitoring/status/"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        health = {}

        # Django (항상 healthy - 응답 가능하므로)
        health['django'] = 'healthy'

        # PostgreSQL
        try:
            from django.db import connection
            connection.ensure_connection()
            health['postgresql'] = 'healthy'
        except Exception:
            health['postgresql'] = 'unhealthy'

        # Redis
        try:
            cache.set('health_check', '1', timeout=5)
            health['redis'] = 'healthy'
        except Exception:
            health['redis'] = 'unhealthy'

        # MySQL legacy
        try:
            with connections['legacy'].cursor() as cursor:
                cursor.execute('SELECT 1')
            health['mysql_legacy'] = 'healthy'
        except Exception:
            health['mysql_legacy'] = 'unhealthy'

        # Celery workers (Redis key 기반 간이 체크)
        # 실제로는 celery inspect를 사용하되 timeout 필요
        health['celery_sync'] = 'unknown'
        health['celery_payment'] = 'unknown'

        # 통계 집계
        today = timezone.now().strftime('%Y%m%d')
        django_reqs = self._sum_routing_stats(f'routing:django:{today}')
        bridge_success = cache.get(f'auth:bridge:success:{today}') or 0
        bridge_fail = self._sum_bridge_failures(today)

        events = EventOutbox.objects.values('status').annotate(
            count=models.Count('id')
        )
        event_summary = {e['status']: e['count'] for e in events}

        return success_response({
            'system': health,
            'routing': {
                'today_django_requests': django_reqs,
            },
            'auth_bridge': {
                'today_success': bridge_success,
                'today_failures': bridge_fail,
                'success_rate': (
                    bridge_success / (bridge_success + bridge_fail)
                    if (bridge_success + bridge_fail) > 0 else 0
                ),
            },
            'events': {
                'pending': event_summary.get('pending', 0),
                'processing': event_summary.get('processing', 0),
                'done_today': EventOutbox.objects.filter(
                    status=EventStatus.DONE,
                    processed_at__date=timezone.now().date(),
                ).count(),
                'failed': event_summary.get('failed', 0),
                'dead_letter': event_summary.get('dead_letter', 0),
            },
            'timestamp': timezone.now().isoformat(),
        })

    @staticmethod
    def _sum_routing_stats(prefix):
        total = 0
        for hour in range(24):
            for method in ('GET', 'POST', 'PUT', 'DELETE', 'PATCH'):
                val = cache.get(f'{prefix}:{hour:02d}:{method}')
                if val:
                    total += int(val)
        return total

    @staticmethod
    def _sum_bridge_failures(date_key):
        total = 0
        for reason in ('session_expired', 'member_not_found', 'django_mapping_failed'):
            val = cache.get(f'auth:bridge:fail:{date_key}:{reason}')
            if val:
                total += int(val)
        return total


class EventRetryView(views.APIView):
    """POST /api/v1/monitoring/events/{id}/retry/"""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            event = EventOutbox.objects.get(pk=pk)
        except EventOutbox.DoesNotExist:
            return error_response('EVENT_002', '이벤트를 찾을 수 없습니다',
                                  http_status=status.HTTP_404_NOT_FOUND)

        if event.status not in (EventStatus.FAILED, EventStatus.DEAD_LETTER):
            return error_response('EVENT_001', '재시도할 수 없는 상태입니다',
                                  details={'current_status': event.status})

        previous_status = event.status
        event.status = EventStatus.PENDING
        event.save(update_fields=['status'])

        return success_response({
            'event_id': event.pk,
            'previous_status': previous_status,
            'new_status': 'pending',
            'retry_count': event.retry_count,
            'message': '이벤트가 재시도 대기열에 추가되었습니다',
        })
```

### 7.4 URL 설정 (monitoring)

**신규 파일**: `apps/monitoring/urls.py`

```python
from django.urls import path
from . import views

urlpatterns = [
    path('status/', views.SystemStatusView.as_view(), name='monitoring-status'),
    path('routing/', views.RoutingStatsView.as_view(), name='monitoring-routing'),
    path('auth/', views.AuthBridgeStatsView.as_view(), name='monitoring-auth'),
    path('events/', views.EventStatsView.as_view(), name='monitoring-events'),
    path('events/<int:pk>/retry/', views.EventRetryView.as_view(), name='monitoring-event-retry'),
]
```

**수정**: `config/urls.py`에 추가

```python
path('api/v1/monitoring/', include('apps.monitoring.urls')),
```

### 7.5 Django Admin 확장

`apps/sync/admin.py`에서 EventOutbox, SyncLog에 대한 Admin 설정:

```python
# apps/sync/admin.py

from django.contrib import admin
from .models import EventOutbox, SyncLog


@admin.register(EventOutbox)
class EventOutboxAdmin(admin.ModelAdmin):
    list_display = ['id', 'source', 'event_type', 'aggregate_type',
                    'aggregate_id', 'status', 'retry_count', 'created_at']
    list_filter = ['source', 'status', 'event_type', 'aggregate_type']
    search_fields = ['aggregate_id', 'correlation_id']
    readonly_fields = ['payload', 'created_at', 'processed_at']
    actions = ['retry_failed_events']

    @admin.action(description='선택한 실패 이벤트 재시도')
    def retry_failed_events(self, request, queryset):
        count = queryset.filter(
            status__in=['failed', 'dead_letter']
        ).update(status='pending')
        self.message_user(request, f'{count}건의 이벤트가 재시도 대기열에 추가되었습니다.')


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ['task_id', 'result', 'processed_count',
                    'failed_count', 'started_at', 'finished_at']
    list_filter = ['result']
    readonly_fields = ['detail']
```

---

## 8. Nginx Configuration

### 8.1 라우팅 규칙 (최종)

기존 아카이브 설계를 기반으로 Phase 2.1 요구사항을 반영한 최종 설정:

```nginx
# /etc/nginx/conf.d/dongta.conf

# Request ID 생성
map $http_x_request_id $request_id {
    default $http_x_request_id;
    ""      $request_id;
}

upstream django_backend {
    server 127.0.0.1:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

upstream php_backend {
    server 127.0.0.1:3000 max_fails=3 fail_timeout=30s;
    keepalive 16;
}

# Rate limiting zone (bridge endpoint)
limit_req_zone $binary_remote_addr zone=bridge_limit:10m rate=10r/m;

server {
    listen 443 ssl http2;
    server_name dongta.theuit.info;

    # Cloudflare SSL (Origin Certificate)
    ssl_certificate     /etc/ssl/dongta/origin.pem;
    ssl_certificate_key /etc/ssl/dongta/origin-key.pem;

    # === API v1 -> Django ===
    location /api/v1/ {
        proxy_pass http://django_backend;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID      $request_id;
        proxy_set_header Connection        "";

        # PHP 세션 쿠키를 Django에 전달
        proxy_set_header Cookie            $http_cookie;

        proxy_connect_timeout 30s;
        proxy_send_timeout    30s;
        proxy_read_timeout    30s;

        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;

        # 재시도 (5xx 에러 시 다음 upstream)
        proxy_next_upstream error timeout http_502 http_503;
        proxy_next_upstream_tries 2;
    }

    # Bridge 엔드포인트 Rate Limiting
    location /api/v1/auth/bridge/ {
        limit_req zone=bridge_limit burst=5 nodelay;
        proxy_pass http://django_backend;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID      $request_id;
        proxy_set_header Cookie            $http_cookie;
    }

    # === API v2 예약 (503) ===
    location /api/v2/ {
        return 503 '{"error":{"code":"NOT_AVAILABLE","message":"API v2 is not yet available"}}';
        add_header Content-Type application/json;
    }

    # === Django Admin ===
    location /admin/ {
        proxy_pass http://django_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # === API Docs ===
    location /api/docs/ {
        proxy_pass http://django_backend;
        proxy_set_header Host $host;
    }

    location /api/schema/ {
        proxy_pass http://django_backend;
        proxy_set_header Host $host;
    }

    # === Static Files (Django) ===
    location /static/ {
        alias /home/ubuntu/work_01/dongta-django/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # === 나머지 전체 -> PHP Apache ===
    location / {
        proxy_pass http://php_backend;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 30s;
        proxy_send_timeout    30s;
        proxy_read_timeout    30s;
    }

    # === Health Check ===
    location /health {
        access_log off;
        return 200 '{"status":"ok"}';
        add_header Content-Type application/json;
    }

    # === Nginx Status (내부 전용) ===
    location /nginx_status {
        stub_status on;
        access_log off;
        allow 127.0.0.1;
        deny all;
    }
}
```

---

## 9. Security Considerations

- [x] PHP 세션 쿠키 위조 방지: MySQL 세션 테이블에서 유효성 검증 후 JWT 발급
- [x] JWT Secret: `settings.SECRET_KEY` 환경변수 관리 (`.env` 파일, Docker Secret)
- [x] Rate Limiting: 브리지 엔드포인트 10req/min per IP (Nginx + Django 이중)
- [x] PHPSESSID 로그 마스킹: 앞 8자만 로깅 (`abc123de...`)
- [ ] HTTPS 강제: Cloudflare SSL 통해 이미 적용, HTTP -> HTTPS 리다이렉트 확인 필요
- [ ] CORS: 브리지 엔드포인트는 same-origin 요청만 허용 (`CORS_ALLOWED_ORIGINS` 검토)
- [ ] MySQL legacy 연결: Read-only 계정 사용 권장 (세션 조회만 필요)
- [ ] Redis JWT 블랙리스트: `rest_framework_simplejwt.token_blacklist` 앱 이미 활성화

---

## 10. Test Plan

### 10.1 Test Scope

| Type | Target | Tool | Coverage |
|------|--------|------|----------|
| Unit Test | SessionBridgeMiddleware | pytest + mock | 세션 조회, 캐시, JWT 생성 |
| Unit Test | BridgeAuthView | pytest + DRF test client | 성공/실패 시나리오 |
| Unit Test | Django Signal Handlers | pytest | EventOutbox 생성 검증 |
| Unit Test | MonitoringViewSet | pytest + DRF test client | 4개 API 응답 형식 |
| Integration Test | MySQL 트리거 | MySQL test DB | INSERT/UPDATE -> TBL_EVENT_OUTBOX |
| Integration Test | Celery process_php_events | pytest-celery | MySQL -> PostgreSQL 이벤트 전파 |
| E2E Test | PHP 세션 -> JWT -> API 호출 | curl / httpie | 전체 인증 플로우 |
| E2E Test | 이벤트 생성 -> Celery 처리 -> 모니터링 확인 | curl + wait | 이벤트 라이프사이클 |
| Load Test | 브리지 엔드포인트 | k6 | 100 concurrent, < 100ms P95 |

### 10.2 Key Test Cases

**SessionBridgeMiddleware**:
- [ ] 유효한 PHPSESSID + 매핑 가능한 회원 -> JWT 자동 발급
- [ ] 유효한 PHPSESSID + Redis 캐시 HIT -> MySQL 조회 스킵
- [ ] 잘못된 PHPSESSID -> JWT 미발급, 요청은 정상 진행 (anonymous)
- [ ] Authorization 헤더 존재 시 -> 미들웨어 스킵
- [ ] MySQL legacy DB 연결 실패 -> 예외 무시, 요청 정상 진행

**BridgeAuthView**:
- [ ] 유효한 세션 -> 200 + JWT + user 정보 반환
- [ ] PHPSESSID 없음 -> 401 BRIDGE_001
- [ ] 세션 만료 -> 401 BRIDGE_002
- [ ] Django 회원 미존재 -> 401 BRIDGE_003
- [ ] Rate Limit 초과 -> 429 BRIDGE_005

**이벤트 로깅**:
- [ ] Member.save(create) -> EventOutbox에 member.insert 레코드 생성
- [ ] Member.save(update) -> EventOutbox에 member.update 레코드 생성
- [ ] MySQL 트리거 -> TBL_EVENT_OUTBOX에 레코드 생성 (별도 MySQL 테스트)

**모니터링**:
- [ ] /monitoring/status/ -> 모든 시스템 health 반환
- [ ] /monitoring/events/{id}/retry/ -> failed 이벤트 pending으로 변경
- [ ] 비관리자 접근 -> 403 Forbidden

### 10.3 Success Criteria

- pytest coverage >= 80% (신규 코드 기준)
- E2E 전체 플로우 3회 연속 성공
- k6 부하 테스트: 브리지 P95 < 100ms, 에러율 < 0.1%

---

## 11. Implementation Order

### Step 1: Nginx 라우팅 최종 확인 & 설정 (Day 1-2)

```
Tasks:
  1.1 현재 Nginx 설정 백업 & 분석
  1.2 위 Section 8 기준으로 Nginx 설정 업데이트
  1.3 X-Request-ID 전파 확인
  1.4 /api/v2/* 503 반환 확인
  1.5 스테이징에서 curl 테스트
```

**Output**: Nginx 설정 파일 배포, curl 테스트 통과

### Step 2: SessionBridgeMiddleware 구현 (Day 3-7)

```
Tasks:
  2.1 PHP 세션 저장소 현황 확인 (파일/Redis/MySQL)
  2.2 RequestIDMiddleware 구현
  2.3 SessionBridgeMiddleware 구현
  2.4 BridgeAuthView, BridgeRevokeView 구현
  2.5 accounts URL 추가
  2.6 settings MIDDLEWARE 순서 설정
  2.7 단위 테스트 작성

Dependencies: PHP 세션 저장소 확인 결과
```

**settings.py MIDDLEWARE 순서**:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'apps.accounts.middleware.RequestIDMiddleware',       # 1st: Request ID
    'apps.monitoring.middleware.RoutingStatsMiddleware',   # 2nd: 통계
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'apps.accounts.middleware.SessionBridgeMiddleware',    # Before Auth
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

**Output**: 세션 브리지 동작, 단위 테스트 통과

### Step 3: 모니터링 API 구현 (Day 8-12)

```
Tasks:
  3.1 apps/monitoring/ 앱 생성
  3.2 RoutingStatsMiddleware 구현
  3.3 4개 모니터링 View 구현
  3.4 monitoring URL 설정
  3.5 Django Admin 이벤트 관리 화면
  3.6 단위 테스트 작성
```

**Output**: 모니터링 API 응답, Admin 화면

### Step 4: 이벤트 로깅 준비 (Day 13-17)

```
Tasks:
  4.1 EventOutbox 모델에 source, correlation_id 추가 (마이그레이션)
  4.2 Django Signal 핸들러 구현 (sync/signals.py)
  4.3 sync apps.py ready() 등록
  4.4 MySQL TBL_EVENT_OUTBOX DDL 실행
  4.5 MySQL 트리거 설치 (테스트 환경 먼저)
  4.6 Celery process_php_events Task 구현
  4.7 Celery Beat 스케줄 추가
  4.8 단위 + 통합 테스트
```

**Output**: 이벤트 기록 동작, Celery 폴링 동작

### Step 5: E2E 테스트 & 스테이징 배포 (Day 18-22)

```
Tasks:
  5.1 E2E 시나리오 작성 (PHP 세션 -> JWT -> API 호출)
  5.2 k6 부하 테스트 실행
  5.3 스테이징 배포 + 72시간 무중단 검증
  5.4 모니터링 대시보드로 현황 확인
  5.5 문서 최종 업데이트
```

**Output**: 스테이징 72시간 안정, Phase 2.1 완료 보고서

---

## 12. Risk Mitigation

| Risk | Impact | Mitigation | Fallback |
|------|--------|-----------|----------|
| PHP 세션 저장소 확인 불가 | Step 2 블록 | Day 1에 서버 접속하여 `php.ini` session 설정 확인 | 세션 테이블 수동 생성 |
| MySQL 트리거 성능 영향 | PHP 쓰기 지연 | 트리거 본문 최소화 (JSON_OBJECT만), 별도 부하 테스트 | 트리거 대신 PHP 훅으로 전환 |
| 세션-JWT 미들웨어 버그 | 인증 실패 | 미들웨어에서 예외 발생 시 무시 (anonymous 진행) | 미들웨어 비활성화 (settings에서 제거) |
| Redis 장애 | 캐시/통계 손실 | Redis Sentinel 고려, 현재는 단일 노드로 시작 | 캐시 없이 MySQL 직접 조회 |
| EventOutbox 마이그레이션 충돌 | 배포 실패 | `--fake` 옵션으로 순서 보장, 스테이징 먼저 테스트 | 수동 ALTER TABLE |
| MySQL legacy DB 읽기 전용 | 트리거 설치 불가 | DBA 권한 확인 | 별도 이벤트 테이블용 DB 사용자 생성 |

---

## 13. Environment Variables (추가 필요)

기존 `.env`에 추가할 변수:

```bash
# Phase 2.1 - 하이브리드 연동
PHP_SESSION_STORAGE=mysql           # file | redis | mysql
PHP_SESSION_REDIS_URL=              # Redis인 경우만
MYSQL_DATABASE_URL=mysql://user:pass@host:3306/dbname  # 이미 존재할 수 있음

# Bridge 설정
BRIDGE_JWT_TTL_MINUTES=15           # 브리지 JWT 기본 TTL (선택, 기본 SIMPLE_JWT 설정 사용)
EVENT_LOG_ENABLED=True              # 이벤트 로깅 활성화

# Monitoring
MONITORING_ADMIN_ONLY=True          # 관리자만 접근 허용
```

---

## 14. Clean Architecture Layer Assignment

| Component | Layer | Location |
|-----------|-------|----------|
| RequestIDMiddleware | Infrastructure | `apps/accounts/middleware.py` |
| SessionBridgeMiddleware | Infrastructure | `apps/accounts/middleware.py` |
| RoutingStatsMiddleware | Infrastructure | `apps/monitoring/middleware.py` |
| BridgeAuthView | Presentation | `apps/accounts/views.py` |
| BridgeRevokeView | Presentation | `apps/accounts/views.py` |
| MonitoringViewSet | Presentation | `apps/monitoring/views.py` |
| EventOutbox (model) | Domain | `apps/sync/models.py` |
| SyncLog (model) | Domain | `apps/sync/models.py` |
| Django Signal Handlers | Application | `apps/sync/signals.py` |
| process_php_events Task | Application | `apps/sync/tasks.py` |
| MySQL Triggers | Infrastructure | `scripts/mysql_triggers.sql` |

---

## 15. Coding Convention Reference

### 15.1 Naming Conventions (Django/Python)

| Target | Rule | Example |
|--------|------|---------|
| View Classes | PascalCase + View suffix | `BridgeAuthView`, `SystemStatusView` |
| Middleware | PascalCase + Middleware suffix | `SessionBridgeMiddleware` |
| Task Functions | snake_case | `process_php_events` |
| URL Patterns | kebab-case | `/api/v1/auth/bridge/` |
| Redis Keys | colon-separated | `session:bridge:{id}` |
| Error Codes | UPPER_SNAKE_CASE | `BRIDGE_001`, `EVENT_001` |
| Log Tags | [UPPER_BRACKET] | `[SYNC]`, `[BRIDGE]`, `[EVENT]` |

### 15.2 Response Format

모든 API는 기존 `core.utils.success_response` / `error_response`를 사용:

```json
// Success
{"success": true, "data": {...}, "error": null}

// Error
{"success": false, "data": null, "error": {"code": "...", "message": "...", "details": ...}}
```

---

## Related Documents

- Plan: [PHP_Django_하이브리드_연동_2.1.plan.md](../../01-plan/features/PHP_Django_하이브리드_연동_2.1.plan.md)
- Archive (Phase 2): [하이브리드_연동.design.md](../../archive/2026-03/하이브리드_연동/하이브리드_연동.design.md)
- Migration Report: [마이그레이션.report.md](../../04-report/features/마이그레이션.report.md)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-03-17 | Phase 2.1 상세 설계 초안 | Team |
