# Phase 5: 배포 후 성능 최적화 및 운영 안정화 Design Document

> **Summary**: View-level Redis 캐싱, Prometheus/Grafana 모니터링 스택, Nginx Canary 배포, DB 쿼리 최적화를 통해 p95 < 500ms 응답시간과 99.9% 가용성을 달성하는 상세 기술 설계
>
> **Project**: dongta.com (PHP+MySQL → Django+PostgreSQL 마이그레이션)
> **Version**: 1.0.0
> **Author**: Frontend Architect
> **Date**: 2026-03-09
> **Status**: Draft
> **Planning Doc**: [Phase_5_배포후_성능_최적화.plan.md](../../01-plan/features/Phase_5_배포후_성능_최적화.plan.md)

---

## 1. Design Goals

1. **성능**: View-level 캐싱으로 반복 조회 응답시간을 70% 이상 단축하고 p95 < 500ms SLA를 달성한다
2. **가시성**: Prometheus + Grafana로 모든 핵심 API의 메트릭을 15초 주기로 수집하고 실시간 대시보드를 구성한다
3. **안정성**: Nginx Canary 가중 라우팅으로 신규 릴리즈를 단계적으로 전환하여 배포 중 다운타임 0초를 보장한다
4. **DB 효율성**: `pg_stat_statements` 기반 슬로우 쿼리 분석과 N+1 제거를 통해 쿼리 응답시간 50% 감소를 달성한다
5. **인프라 재사용**: 기존 Redis, Celery, Nginx, Docker Compose 인프라를 확장하여 추가 인프라 비용을 최소화한다

---

## 2. Architecture Overview

### 2.1 전체 시스템 구조

```
                         Internet
                            │
                       ┌────▼────┐
                       │  Nginx  │  (Load Balancer + TLS)
                       │ :80/443 │
                       └────┬────┘
                            │ Canary Weighted Routing
              ┌─────────────┴──────────────┐
              │ weight=90                  │ weight=10
       ┌──────▼───────┐          ┌─────────▼──────┐
       │  web_v0:8000 │          │ web_v1:8000    │
       │  (Stable)    │          │ (Canary)       │
       └──────┬───────┘          └─────────┬──────┘
              │                            │
              └────────────┬───────────────┘
                           │
                    ┌──────▼──────┐
                    │Django App   │
                    │ + Prometheus│
                    │ Middleware  │
                    └──────┬──────┘
                    ┌──────┴──────────────────┐
              ┌─────▼─────┐          ┌────────▼──────┐
              │   Redis   │          │  PostgreSQL   │
              │ Cache DB1 │          │  + pg_stat_   │
              │ Queue DB0 │          │  statements   │
              └─────┬─────┘          └───────────────┘
                    │
       ┌────────────┴──────────────────┐
       │          Monitoring Stack      │
       │  ┌───────────┐  ┌──────────┐ │
       │  │Prometheus │  │ Grafana  │ │
       │  │ :9090     │  │  :3000   │ │
       │  └───────────┘  └──────────┘ │
       │  ┌────────────┐              │
       │  │Node Exporter│             │
       │  │ :9100       │             │
       └──└────────────┘──────────────┘
```

### 2.2 Caching Layer 흐름

```
Client Request
      │
      ▼
  Nginx (upstream)
      │
      ▼
  Django View (@cache_page 적용)
      │
      ├─ Cache HIT ──▶ Redis (DB=1) ──▶ Response (X-Cache-Hit: true)
      │
      └─ Cache MISS ──▶ DB Query (PostgreSQL)
                            │
                            ▼
                        Cache Store (Redis, TTL)
                            │
                            ▼
                        Response (X-Cache-Hit: false)
```

### 2.3 Metrics Collection 흐름

```
Django App
  ├── PrometheusBeforeMiddleware  (request count, latency histogram)
  ├── PrometheusAfterMiddleware   (response code, response size)
  ├── Custom Metrics              (cache hit rate, db query count)
  └── /metrics endpoint (port 8000)
        │
  Prometheus (scrape interval: 15s, retention: 15d)
        │
  Grafana (실시간 대시보드 + AlertManager)
        │
  Alert Channels: Slack / Email
```

---

## 3. Component Design

### 3.A View-level Caching

#### 3.A.1 적용 대상 엔드포인트

| 엔드포인트 | TTL | Cache Key 패턴 | 예상 Hit Rate |
|-----------|-----|----------------|--------------|
| `GET /api/v1/recruit/jobs/` | 300s (5분) | `dongta:recruit:jobs:page:{page}:sort:{sort}:cat:{category}` | > 70% |
| `GET /api/v1/recruit/jobs/{id}/` | 600s (10분) | `dongta:recruit:jobs:detail:{id}` | > 80% |
| `GET /api/v1/business114/` | 300s (5분) | `dongta:business114:list:sort:{sort}:type:{type}` | > 70% |
| `GET /api/v1/business114/{id}/` | 600s (10분) | `dongta:business114:detail:{id}` | > 80% |
| `GET /api/v1/recruit/common-codes/` | 3600s (1시간) | `dongta:recruit:common-codes` | > 95% |

**인증 필요 엔드포인트 (캐싱 제외)**:
- `POST`, `PUT`, `PATCH`, `DELETE` 모든 변경 엔드포인트
- 사용자별 개인화 데이터 (`/api/v1/mypage/`, `/api/v1/payment/`)

#### 3.A.2 Redis Cache 설정

```python
# config/settings/base.py 확장
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://redis:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'IGNORE_EXCEPTIONS': True,  # Redis 장애 시 폴백 허용
        },
        'KEY_PREFIX': 'dongta',
        'TIMEOUT': 300,
        'VERSION': 1,
    }
}

# Cache Middleware 설정
CACHE_MIDDLEWARE_SECONDS = env.int('CACHE_MIDDLEWARE_SECONDS', default=300)
CACHE_MIDDLEWARE_KEY_PREFIX = env('CACHE_MIDDLEWARE_KEY_PREFIX', default='dongta')
```

**Redis DB 분리 전략**:
- `DB=0`: Celery broker (기존 유지)
- `DB=1`: View cache (신규 추가)
- `DB=2`: Session (운영 환경)

#### 3.A.3 View Decorator 적용 패턴

```python
# apps/recruit/views.py
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from django.utils.decorators import method_decorator

@method_decorator(
    cache_page(60 * 5, cache='default', key_prefix='recruit:jobs'),
    name='list'
)
class JobViewSet(viewsets.ModelViewSet):
    """채용공고 ViewSet"""

    def list(self, request, *args, **kwargs):
        # 인증된 사용자는 별도 캐시 키 사용 (로그인 상태 미반영 방지)
        response = super().list(request, *args, **kwargs)
        response['X-Cache-Key'] = self._build_cache_key(request)
        return response

    def _build_cache_key(self, request):
        page = request.query_params.get('page', '1')
        sort = request.query_params.get('sort', 'latest')
        category = request.query_params.get('category', 'all')
        return f"recruit:jobs:page:{page}:sort:{sort}:cat:{category}"
```

#### 3.A.4 Cache Invalidation 전략

Signal 기반 자동 무효화:

```python
# apps/recruit/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Job

@receiver([post_save, post_delete], sender=Job)
def invalidate_job_cache(sender, instance, **kwargs):
    """채용공고 변경 시 관련 캐시 전체 무효화"""
    # 패턴 기반 삭제 (django-redis의 delete_pattern 활용)
    cache.delete_pattern('dongta:recruit:jobs:*')


# apps/business114/signals.py
@receiver([post_save, post_delete], sender=Business)
def invalidate_business_cache(sender, instance, **kwargs):
    cache.delete_pattern('dongta:business114:*')
    cache.delete(f'dongta:business114:detail:{instance.pk}')
```

---

### 3.B Prometheus Metrics

#### 3.B.1 패키지 및 설정

```python
# config/settings/base.py
INSTALLED_APPS = [
    ...
    'django_prometheus',  # THIRD_PARTY_APPS에 추가 (맨 앞 위치 필수)
    ...
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',  # 첫 번째
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    ...
    'django_prometheus.middleware.PrometheusAfterMiddleware',   # 마지막
]
```

```python
# config/urls.py
from django_prometheus import exports as prometheus_views

urlpatterns = [
    ...
    path('metrics/', prometheus_views.ExportToDjangoView, name='prometheus-metrics'),
]
```

#### 3.B.2 자동 수집 메트릭 (django-prometheus 기본 제공)

| 메트릭 이름 | 유형 | 설명 |
|------------|------|------|
| `django_http_requests_total_by_method_total` | Counter | HTTP 메서드별 요청 수 |
| `django_http_requests_latency_seconds_by_view_method` | Histogram | View별 응답시간 분포 |
| `django_http_responses_total_by_status_total` | Counter | HTTP 상태코드별 응답 수 |
| `django_db_execute_total` | Counter | DB 쿼리 실행 수 |
| `django_cache_get_total` | Counter | 캐시 GET 호출 수 |
| `django_cache_get_hits_total` | Counter | 캐시 HIT 수 |
| `django_cache_get_misses_total` | Counter | 캐시 MISS 수 |

#### 3.B.3 커스텀 메트릭

```python
# core/metrics.py
from prometheus_client import Histogram, Gauge, Counter

# 요청 응답시간 (뷰 단위 세분화)
REQUEST_LATENCY = Histogram(
    'dongta_request_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint', 'status_code'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# DB 쿼리 수 (요청당)
DB_QUERY_COUNT = Gauge(
    'dongta_db_query_count_per_request',
    'Number of DB queries per request',
    ['endpoint'],
)

# Cache hit rate (계산값)
CACHE_HIT_RATE = Gauge(
    'dongta_cache_hit_rate',
    'Cache hit rate (0.0 to 1.0)',
    ['cache_prefix'],
)

# Canary 트래픽 비율
CANARY_TRAFFIC_RATIO = Gauge(
    'dongta_canary_traffic_ratio',
    'Current canary traffic weight (0.0 to 1.0)',
)
```

#### 3.B.4 Prometheus Scrape 설정

```yaml
# monitoring/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    environment: 'production'
    project: 'dongta'

rule_files:
  - "rules/alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  - job_name: 'django'
    static_configs:
      - targets: ['web:8000']
    metrics_path: '/metrics/'
    scrape_interval: 15s

  - job_name: 'django_canary'
    static_configs:
      - targets: ['web_v1:8000']
    metrics_path: '/metrics/'
    scrape_interval: 15s

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'celery'
    static_configs:
      - targets: ['celery-exporter:9808']

storage:
  tsdb:
    retention.time: 15d
    retention.size: 10GB
```

---

### 3.C Grafana Dashboard

#### 3.C.1 대시보드 구성 (dongta-overview.json)

**Row 1: 트래픽 & 응답시간**

| 패널 | 유형 | PromQL |
|------|------|--------|
| 초당 요청수 (RPS) | Time series | `rate(django_http_requests_total_by_method_total[5m])` |
| p95 응답시간 | Gauge | `histogram_quantile(0.95, rate(django_http_requests_latency_seconds_by_view_method_bucket[5m]))` |
| p99 응답시간 | Gauge | `histogram_quantile(0.99, rate(django_http_requests_latency_seconds_by_view_method_bucket[5m]))` |
| 응답시간 분포 | Heatmap | `rate(django_http_requests_latency_seconds_by_view_method_bucket[5m])` |

**Row 2: 오류율 & 가용성**

| 패널 | 유형 | PromQL |
|------|------|--------|
| 오류율 (5xx) | Stat | `rate(django_http_responses_total_by_status_total{status=~"5.."}[5m]) / rate(django_http_responses_total_by_status_total[5m])` |
| 4xx 비율 | Time series | `rate(django_http_responses_total_by_status_total{status=~"4.."}[5m])` |
| 업타임 (SLO) | Gauge | `1 - (rate(django_http_responses_total_by_status_total{status=~"5.."}[24h]) / rate(django_http_responses_total_by_status_total[24h]))` |

**Row 3: Cache 성능**

| 패널 | 유형 | PromQL |
|------|------|--------|
| Cache Hit Rate | Gauge | `rate(django_cache_get_hits_total[5m]) / (rate(django_cache_get_hits_total[5m]) + rate(django_cache_get_misses_total[5m]))` |
| Cache Hits/Misses | Time series | `rate(django_cache_get_hits_total[5m])`, `rate(django_cache_get_misses_total[5m])` |
| Redis 메모리 사용 | Gauge | `redis_memory_used_bytes / redis_memory_max_bytes` |

**Row 4: DB 성능**

| 패널 | 유형 | PromQL |
|------|------|--------|
| DB 쿼리 수/분 | Time series | `rate(django_db_execute_total[1m]) * 60` |
| Active DB Connections | Gauge | `pg_stat_activity_count{state="active"}` |
| DB 응답시간 | Histogram | `histogram_quantile(0.95, rate(pg_query_duration_seconds_bucket[5m]))` |

**Row 5: 시스템 리소스**

| 패널 | 유형 | PromQL |
|------|------|--------|
| CPU 사용률 | Gauge | `100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)` |
| 메모리 사용률 | Gauge | `(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100` |
| Celery 큐 길이 | Time series | `celery_tasks_waiting` |

#### 3.C.2 Alert Rules

```yaml
# monitoring/prometheus/rules/alert_rules.yml
groups:
  - name: dongta_slo
    interval: 30s
    rules:
      - alert: HighP95Latency
        expr: histogram_quantile(0.95, rate(django_http_requests_latency_seconds_by_view_method_bucket[5m])) > 0.5
        for: 5m
        labels:
          severity: warning
          team: backend
        annotations:
          summary: "p95 응답시간 임계값 초과"
          description: "p95 응답시간이 {{ $value | humanizeDuration }} (임계값: 500ms)"

      - alert: CriticalP95Latency
        expr: histogram_quantile(0.95, rate(django_http_requests_latency_seconds_by_view_method_bucket[5m])) > 1.0
        for: 2m
        labels:
          severity: critical
          team: backend
        annotations:
          summary: "p95 응답시간 위험 수준"
          description: "p95 응답시간이 {{ $value | humanizeDuration }} — 즉시 조사 필요"

      - alert: HighErrorRate
        expr: rate(django_http_responses_total_by_status_total{status=~"5.."}[5m]) / rate(django_http_responses_total_by_status_total[5m]) > 0.01
        for: 3m
        labels:
          severity: critical
          team: backend
        annotations:
          summary: "오류율 1% 초과"
          description: "현재 오류율: {{ $value | humanizePercentage }}"

      - alert: LowCacheHitRate
        expr: rate(django_cache_get_hits_total[10m]) / (rate(django_cache_get_hits_total[10m]) + rate(django_cache_get_misses_total[10m])) < 0.7
        for: 10m
        labels:
          severity: warning
          team: backend
        annotations:
          summary: "Cache hit rate 70% 미만"
          description: "현재 cache hit rate: {{ $value | humanizePercentage }}"

      - alert: HighDBConnections
        expr: pg_stat_activity_count{state="active"} > 18
        for: 5m
        labels:
          severity: warning
          team: devops
        annotations:
          summary: "DB active connection 수 과다"
          description: "Active connections: {{ $value }} / 20 (pool max)"

      - alert: HighCPUUsage
        expr: 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 70
        for: 10m
        labels:
          severity: warning
          team: devops
        annotations:
          summary: "CPU 사용률 70% 초과"
          description: "CPU: {{ $value }}%"

      - alert: CanaryHighErrorRate
        expr: rate(django_http_responses_total_by_status_total{job="django_canary",status=~"5.."}[5m]) / rate(django_http_responses_total_by_status_total{job="django_canary"}[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
          team: devops
          action: rollback
        annotations:
          summary: "Canary 인스턴스 오류율 5% 초과 — 롤백 필요"
          description: "Canary 오류율: {{ $value | humanizePercentage }}"
```

---

### 3.D Canary Deployment

#### 3.D.1 Nginx 가중 Upstream 설정

```nginx
# nginx/conf.d/upstream.conf

# Stable 인스턴스 (v0)
upstream backend_v0 {
    server web_v0:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

# Canary 인스턴스 (v1)
upstream backend_v1 {
    server web_v1:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

# Canary 가중 upstream (가중치는 단계에 따라 변경)
upstream backend_canary {
    server web_v0:8000 weight=90;  # 단계 1: 10% → 단계 4: 0%
    server web_v1:8000 weight=10;  # 단계 1: 10% → 단계 4: 100%
    keepalive 32;
}
```

```nginx
# nginx/conf.d/dongta.conf

server {
    listen 80;
    server_name dongta.com www.dongta.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dongta.com www.dongta.com;

    # SSL 설정 (기존 유지)
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # 응답 헤더 추가 (모니터링 및 디버깅)
    add_header X-Response-Time $upstream_response_time;
    add_header X-Upstream-Addr $upstream_addr;

    # Health Check 엔드포인트 (모든 트래픽에서 stable로)
    location /api/v1/health/ {
        proxy_pass http://backend_v0;
        access_log off;
    }

    # Prometheus metrics (내부 접근만 허용)
    location /metrics/ {
        allow 172.16.0.0/12;  # Docker 내부 네트워크
        deny all;
        proxy_pass http://backend_canary;
    }

    # API 트래픽 (Canary 가중 라우팅)
    location /api/ {
        proxy_pass http://backend_canary;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_read_timeout 30s;
        proxy_send_timeout 10s;
    }

    # 정적 파일 (기존 유지)
    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }
}
```

#### 3.D.2 단계별 트래픽 전환 계획

| 단계 | 기간 | web_v0 가중치 | web_v1 가중치 | 롤백 조건 |
|------|------|--------------|--------------|----------|
| Step 0 (배포 전) | Staging 검증 | 100% | 0% | - |
| Step 1 (Canary 시작) | Day 1-2 | 90% | 10% | 오류율 > 5% or p95 > 1000ms |
| Step 2 | Day 3-4 | 70% | 30% | 오류율 > 1% or p95 > 700ms |
| Step 3 | Day 5-6 | 50% | 50% | 오류율 > 1% or p95 > 600ms |
| Step 4 (완전 전환) | Day 7+ | 0% | 100% | 오류율 > 0.5% or p95 > 500ms |

#### 3.D.3 Canary 가중치 변경 스크립트

```bash
#!/bin/bash
# scripts/canary-switch.sh

STEP=$1  # 1, 2, 3, 4

case $STEP in
  1)
    V0_WEIGHT=90; V1_WEIGHT=10 ;;
  2)
    V0_WEIGHT=70; V1_WEIGHT=30 ;;
  3)
    V0_WEIGHT=50; V1_WEIGHT=50 ;;
  4)
    V0_WEIGHT=0; V1_WEIGHT=100 ;;
  rollback)
    V0_WEIGHT=100; V1_WEIGHT=0 ;;
  *)
    echo "Usage: $0 {1|2|3|4|rollback}"; exit 1 ;;
esac

# upstream.conf 파일 업데이트
sed -i \
  -e "s/web_v0:8000 weight=[0-9]*/web_v0:8000 weight=$V0_WEIGHT/" \
  -e "s/web_v1:8000 weight=[0-9]*/web_v1:8000 weight=$V1_WEIGHT/" \
  /etc/nginx/conf.d/upstream.conf

# Nginx reload (무중단)
nginx -t && nginx -s reload
echo "Canary Step $STEP: v0=$V0_WEIGHT%, v1=$V1_WEIGHT%"
```

#### 3.D.4 Health Check 엔드포인트

```python
# apps/core/views.py 또는 config/urls.py에 추가

from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import time

def health_check(request):
    """Health check endpoint for Nginx upstream"""
    checks = {}
    status_code = 200

    # DB 연결 확인
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks['db'] = 'ok'
    except Exception as e:
        checks['db'] = f'error: {str(e)}'
        status_code = 503

    # Redis 연결 확인
    try:
        cache.set('health_check', '1', timeout=5)
        checks['cache'] = 'ok'
    except Exception as e:
        checks['cache'] = f'error: {str(e)}'
        # Redis 장애는 503으로 처리하지 않음 (IGNORE_EXCEPTIONS=True)

    return JsonResponse({
        'status': 'ok' if status_code == 200 else 'degraded',
        'checks': checks,
        'timestamp': time.time(),
    }, status=status_code)
```

```nginx
# Nginx upstream health check (nginx plus 또는 오픈소스 대안)
upstream backend_v0 {
    server web_v0:8000;

    # 오픈소스 Nginx: passive health check
    # max_fails=3: 30초 내 3회 실패 시 제외
    # fail_timeout=30s: 30초 후 재시도
}
```

---

## 4. Data Model Changes

Phase 5는 기존 애플리케이션 데이터 스키마를 변경하지 않는다. 캐시와 메트릭은 Redis와 Prometheus의 자체 스토리지를 사용한다.

### 4.1 Cache 스토리지 (Redis)

| 항목 | 값 |
|------|---|
| Backend | Redis 7 (기존 인프라) |
| Database | DB=1 (신규, DB=0은 Celery 전용 유지) |
| Key Format | `{KEY_PREFIX}:{app}:{resource}:{params}` |
| Serializer | JSON |
| Max Memory | `maxmemory 512mb` (redis.conf 설정 권고) |
| Eviction Policy | `allkeys-lru` (메모리 초과 시 LRU 제거) |

### 4.2 Prometheus Time-series 스토리지

| 항목 | 값 |
|------|---|
| 보존 기간 | 15일 |
| 보존 용량 | 10GB |
| 스크레이프 간격 | 15초 |
| 데이터 디렉토리 | Docker volume `prometheus_data` |

---

## 5. API Changes

### 5.1 신규 엔드포인트

| 엔드포인트 | 설명 | 인증 |
|-----------|------|------|
| `GET /api/v1/health/` | Health check (Nginx upstream용) | 불필요 |
| `GET /metrics/` | Prometheus scrape endpoint | IP 화이트리스트 (내부망만) |

### 5.2 응답 헤더 추가

기존 엔드포인트 응답에 다음 헤더를 추가한다:

| 헤더 | 값 예시 | 설명 |
|------|--------|------|
| `X-Cache-Hit` | `true` / `false` | Redis 캐시 히트 여부 |
| `X-Response-Time` | `0.123` | Nginx upstream 응답시간 (초) |
| `X-Upstream-Addr` | `172.18.0.5:8000` | 처리한 upstream 주소 (Canary 디버깅용) |

`X-Cache-Hit` 헤더는 DRF의 커스텀 미들웨어로 주입한다:

```python
# core/middleware.py
class CacheHitHeaderMiddleware:
    """캐시 히트 여부를 응답 헤더에 추가"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # django-redis가 설정한 캐시 히트 여부 확인
        if hasattr(response, 'from_cache'):
            response['X-Cache-Hit'] = str(response.from_cache).lower()
        else:
            response['X-Cache-Hit'] = 'false'
        return response
```

---

## 6. Implementation Details

### 6.1 패키지 의존성 추가

```txt
# requirements/base.txt 추가 항목
django-redis==5.4.0        # Redis cache backend (django_redis.cache.RedisCache)
django-prometheus==0.3.1   # Prometheus metrics export

# requirements/production.txt 추가 항목
celery-prometheus-exporter==1.7.0  # Celery 메트릭 (FR-09, Could 항목)
```

### 6.2 Docker Compose 모니터링 스택 추가

```yaml
# docker-compose.monitoring.yml (신규 파일)
version: '3.9'

services:
  prometheus:
    image: prom/prometheus:v2.50.0
    volumes:
      - ./monitoring/prometheus:/etc/prometheus:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=15d'
      - '--storage.tsdb.retention.size=10GB'
      - '--web.enable-lifecycle'
    ports:
      - "127.0.0.1:9090:9090"  # 로컬호스트만 노출
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.3.0
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards:ro
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=https://monitoring.dongta.com
    ports:
      - "127.0.0.1:3000:3000"  # 로컬호스트만 노출 (Nginx 리버스프록시 경유)
    depends_on:
      - prometheus
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:v1.7.0
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
    ports:
      - "127.0.0.1:9100:9100"
    restart: unless-stopped

  redis-exporter:
    image: oliver006/redis_exporter:v1.57.0
    environment:
      - REDIS_ADDR=redis://redis:6379
    ports:
      - "127.0.0.1:9121:9121"
    depends_on:
      - redis
    restart: unless-stopped

  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:v0.15.0
    environment:
      - DATA_SOURCE_NAME=${DATABASE_URL}
    ports:
      - "127.0.0.1:9187:9187"
    depends_on:
      - db
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:v0.26.0
    volumes:
      - ./monitoring/alertmanager:/etc/alertmanager:ro
    ports:
      - "127.0.0.1:9093:9093"
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
```

### 6.3 DB 쿼리 최적화

#### Connection Pool 설정

```python
# config/settings/production.py 추가
DATABASES = {
    'default': {
        **env.db('DATABASE_URL'),
        'CONN_MAX_AGE': 60,  # 커넥션 재사용 (초)
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000',  # 30초 쿼리 타임아웃
        },
    }
}
```

#### pg_stat_statements 활성화

```sql
-- PostgreSQL 설정 (postgresql.conf)
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.max = 10000
pg_stat_statements.track = all

-- 확장 설치 (초기화 시 한 번)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

#### Slow Query 탐지 쿼리

```sql
-- 상위 10개 슬로우 쿼리 조회
SELECT
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    rows,
    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

#### 예상 N+1 수정 대상

| 앱 | 쿼리 패턴 | 수정 방법 |
|----|---------|---------|
| `recruit` | JobViewSet에서 Company 정보 개별 조회 | `select_related('company')` |
| `recruit` | JobViewSet에서 Tags 개별 조회 | `prefetch_related('tags')` |
| `business114` | BusinessViewSet에서 Category 개별 조회 | `select_related('category')` |
| `board` | PostViewSet에서 Author 개별 조회 | `select_related('author')` |

#### 인덱스 추가 계획

```sql
-- recruit_job 테이블
CREATE INDEX CONCURRENTLY idx_recruit_job_status_created
    ON recruit_job (status, created_at DESC)
    WHERE status = 'active';

CREATE INDEX CONCURRENTLY idx_recruit_job_company_id
    ON recruit_job (company_id);

-- business114 테이블
CREATE INDEX CONCURRENTLY idx_business114_category_id
    ON business114_business (category_id);

CREATE INDEX CONCURRENTLY idx_business114_is_active
    ON business114_business (is_active, created_at DESC)
    WHERE is_active = true;
```

---

## 7. Deployment Strategy

### 7.1 Staging 환경 구성

```yaml
# docker-compose.staging.yml (신규)
version: '3.9'

# 모든 서비스를 단일 호스트에서 실행
# 모니터링 스택 포함 (full monitoring)
# 프로덕션과 동일한 환경변수 구조 사용
```

**Staging 검증 체크리스트 (Week 1)**:

- [ ] Docker Compose staging 정상 시작
- [ ] `/api/v1/health/` 응답 확인
- [ ] `/metrics/` Prometheus 스크레이프 성공 확인
- [ ] Redis cache hit 확인 (Redis Monitor 또는 `redis-cli monitor`)
- [ ] Grafana 대시보드 패널 정상 렌더링 확인
- [ ] Alert rule 테스트 발송 확인
- [ ] 부하 테스트: 50 concurrent users, p95 < 500ms

### 7.2 Production Canary 배포 순서

```
Day 0: 모니터링 스택 먼저 배포 (Prometheus, Grafana)
         ↓
Day 1: web_v1 컨테이너 빌드 및 배포 (weight=0, 트래픽 없음)
         ↓
Day 1 (오후): Canary Step 1 시작 (weight=10%)
         ↓ 48시간 모니터링
Day 3: Canary Step 2 (weight=30%)
         ↓ 48시간 모니터링
Day 5: Canary Step 3 (weight=50%)
         ↓ 48시간 모니터링
Day 7+: Canary Step 4 완전 전환 (weight=100%)
         ↓
         web_v0 종료 (web_v1이 안정적으로 동작 확인 후)
```

### 7.3 롤백 절차

**자동 롤백 조건** (Prometheus Alert → AlertManager → 롤백 스크립트):
- Canary 오류율 > 5% (2분 지속)
- Canary p95 응답시간 > 1000ms (5분 지속)

**수동 롤백 명령**:
```bash
# 즉시 롤백 (트래픽 100% v0으로)
bash /app/scripts/canary-switch.sh rollback

# 상태 확인
curl -s http://localhost/api/v1/health/ | jq .
```

---

## 8. Testing Plan

### 8.1 Unit Tests

| 테스트 항목 | 파일 위치 | 검증 내용 |
|------------|---------|---------|
| Cache hit 동작 | `apps/recruit/tests/test_cache.py` | `@cache_page` 적용 후 두 번째 호출 시 DB 쿼리 0회 |
| Cache invalidation | `apps/recruit/tests/test_cache.py` | Job 저장 시 캐시 키 삭제 확인 |
| Cache miss fallthrough | `core/tests/test_cache.py` | Redis 장애 시 DB 직접 조회로 폴백 |
| Health check 응답 | `core/tests/test_health.py` | DB/Redis 정상 시 200, DB 장애 시 503 |

```python
# apps/recruit/tests/test_cache.py 예시
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

class JobCacheTest(TestCase):

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_list_endpoint_cached_on_second_call(self):
        """두 번째 호출은 캐시에서 응답해야 함"""
        url = reverse('recruit:job-list')

        with self.assertNumQueries(3):  # 첫 번째 호출: DB 쿼리 발생
            response1 = self.client.get(url)

        with self.assertNumQueries(0):  # 두 번째 호출: 캐시에서 응답 (DB 쿼리 0)
            response2 = self.client.get(url)

        self.assertEqual(response1.data, response2.data)
```

### 8.2 Integration Tests

| 테스트 항목 | 검증 방법 |
|------------|---------|
| Prometheus scrape | `curl localhost:8000/metrics/` 응답에서 `django_http_requests_total` 존재 확인 |
| Grafana datasource | Grafana API `/api/datasources/proxy/1/api/v1/query` 성공 응답 |
| Canary routing | Nginx upstream 가중치 변경 후 100회 요청 중 v1 응답 비율이 weight와 일치 여부 확인 |

### 8.3 Load Tests (k6 또는 locust)

**목표 시나리오**:
```
100 concurrent users
Duration: 10 minutes
Ramp-up: 2 minutes

Endpoints:
- GET /api/v1/recruit/jobs/         (40%)
- GET /api/v1/business114/          (30%)
- GET /api/v1/recruit/jobs/{id}/    (20%)
- GET /api/v1/recruit/common-codes/ (10%)
```

**합격 기준**:
- p95 응답시간 < 500ms
- 오류율 < 0.1%
- Cache hit rate > 70% (10분 후 측정)
- CPU 사용률 < 70%

### 8.4 Canary Monitoring Checklist

Canary 각 단계 전환 전 확인사항:

- [ ] Grafana에서 Canary 인스턴스 오류율 < 1%
- [ ] Canary p95 응답시간 < 500ms
- [ ] Canary cache hit rate >= stable 인스턴스 대비 -5% 이내
- [ ] DB active connection 수 < 18
- [ ] 서버 CPU < 70%, 메모리 < 80%

---

## 9. Monitoring & Alerts

### 9.1 모니터링 레이어

| 레이어 | 도구 | 목적 | 이미 구성 여부 |
|-------|------|------|--------------|
| Error Tracking | Sentry | 예외 캡처, 스택 트레이스 | ✅ Phase 3에서 완료 |
| Metrics | Prometheus | 시계열 메트릭 수집 | 신규 (Phase 5) |
| Visualization | Grafana | 대시보드, 알림 | 신규 (Phase 5) |
| APM (개발) | django-debug-toolbar | 쿼리 프로파일링 | 신규 (Phase 5) |
| APM (운영) | New Relic (선택) | 심층 프로파일링 | 선택사항 |

### 9.2 SLO 대시보드 요약

| SLO | 목표 | 측정 주기 | Alert 임계값 |
|-----|------|---------|------------|
| Availability | > 99.9% | 1시간 | < 99.5% → Critical |
| p95 Latency | < 500ms | 5분 | > 500ms → Warning, > 1000ms → Critical |
| Cache Hit Rate | > 70% | 10분 | < 70% → Warning |
| Error Rate | < 0.1% | 5분 | > 1% → Critical |
| DB Connections | < 18 | 5분 | > 18 → Warning |

### 9.3 운영 Runbook (Alert 대응 절차)

**HighP95Latency (p95 > 500ms)**:
1. Grafana에서 어떤 View가 느린지 확인 (`django_http_requests_latency_seconds_by_view_method`)
2. pg_stat_statements에서 해당 View의 쿼리 시간 확인
3. Redis cache hit rate 확인 (캐시 miss가 급증했는지)
4. Canary 배포 중이면 가중치 롤백 검토

**HighErrorRate (오류율 > 1%)**:
1. Sentry에서 최신 오류 확인
2. Nginx access log에서 어떤 엔드포인트가 5xx인지 확인
3. Canary 배포 중이면 즉시 rollback 실행

**LowCacheHitRate (hit rate < 70%)**:
1. Redis 메모리 사용량 확인 (`redis-cli info memory`)
2. 캐시 무효화 Signal이 과도하게 발생하는지 확인
3. `redis-cli --scan --pattern "dongta:*" | wc -l`로 키 수 확인

---

## 10. Implementation Order (Step-by-step)

### Week 1: Staging + Cache 설정

1. `django-redis` 설치 및 `CACHES` 설정 업데이트
2. `django_prometheus` 설치 및 `INSTALLED_APPS`, `MIDDLEWARE` 설정
3. `/api/v1/health/` 엔드포인트 구현
4. `@cache_page` 데코레이터 recruit, business114 ViewSet에 적용
5. Cache invalidation Signal 구현 (recruit, business114)
6. `docker-compose.staging.yml` 작성 및 Staging 환경 시작
7. Redis Monitor로 cache hit 동작 확인
8. `CacheHitHeaderMiddleware` 구현 및 적용

### Week 2: Prometheus + Grafana

1. `monitoring/prometheus/prometheus.yml` 작성
2. `monitoring/prometheus/rules/alert_rules.yml` 작성
3. `monitoring/grafana/provisioning/` datasource 및 dashboard 설정
4. `docker-compose.monitoring.yml` 작성
5. Prometheus, Grafana, Node Exporter, Redis Exporter 기동
6. Grafana 대시보드 패널 구성 및 Alert 설정
7. AlertManager Slack/Email 연동 설정
8. Grafana에서 전체 패널 정상 렌더링 확인

### Week 3: Canary 배포

1. `nginx/conf.d/upstream.conf` Canary 가중 upstream 설정
2. `scripts/canary-switch.sh` 작성 및 권한 부여
3. web_v1 컨테이너 빌드 및 배포 (초기 weight=0)
4. Canary Step 1 시작 (10%) + Grafana 모니터링 시작
5. 48시간 후 Canary Step 2 (30%) 전환
6. Nginx upstream health check passive 설정 확인

### Week 4: 성능 튜닝

1. `pg_stat_statements` 확성화 및 슬로우 쿼리 Top 10 추출
2. N+1 쿼리 식별 및 `select_related` / `prefetch_related` 적용
3. Migration 생성 및 적용 (인덱스 추가)
4. django-debug-toolbar 개발 환경 설정
5. k6 또는 locust 부하 테스트 실행
6. Canary Step 3 (50%) → Step 4 (100%) 전환
7. Cache hit rate 70% 달성 여부 Grafana에서 최종 확인

---

## 11. File Structure

```
dongta-django/
├── config/settings/
│   ├── base.py              (CACHES, django_prometheus 추가)
│   └── production.py        (DATABASES CONN_MAX_AGE, Connection Pool)
│
├── core/
│   ├── middleware.py         (CacheHitHeaderMiddleware 신규)
│   ├── metrics.py            (커스텀 Prometheus 메트릭 신규)
│   └── views.py              (health_check view 신규)
│
├── apps/recruit/
│   ├── views.py              (@cache_page 데코레이터 추가)
│   └── signals.py            (cache invalidation 신규)
│
├── apps/business114/
│   ├── views.py              (@cache_page 데코레이터 추가)
│   └── signals.py            (cache invalidation 신규)
│
├── nginx/conf.d/
│   └── upstream.conf         (Canary weighted upstream 신규)
│
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   └── rules/
│   │       └── alert_rules.yml
│   ├── grafana/
│   │   ├── provisioning/
│   │   │   ├── datasources/prometheus.yml
│   │   │   └── dashboards/dashboards.yml
│   │   └── dashboards/
│   │       └── dongta-overview.json
│   └── alertmanager/
│       └── alertmanager.yml
│
├── scripts/
│   └── canary-switch.sh      (신규)
│
├── docker-compose.staging.yml    (신규)
└── docker-compose.monitoring.yml (신규)
```

---

## 12. Environment Variables

| 변수명 | 용도 | 범위 | 예시 값 |
|--------|------|------|--------|
| `REDIS_URL` | Redis 연결 URL (기존) | Server | `redis://redis:6379/0` |
| `CACHE_MIDDLEWARE_SECONDS` | View cache TTL (초) | Server | `300` |
| `CACHE_MIDDLEWARE_KEY_PREFIX` | Cache key prefix | Server | `dongta` |
| `GRAFANA_ADMIN_PASSWORD` | Grafana 관리자 비밀번호 | Server | (random string) |
| `PROMETHEUS_METRICS_EXPORT_PORT` | Prometheus scrape 포트 | Server | `8000` |
| `SLOW_QUERY_THRESHOLD_MS` | Slow query 로그 임계값 | Server | `100` |
| `NEWRELIC_LICENSE_KEY` | New Relic APM 키 (선택) | Server | (license key) |

---

## 13. Risks

| Risk | 완화 방안 |
|------|---------|
| Redis 장애 시 전체 API 중단 | `IGNORE_EXCEPTIONS: True` 설정으로 캐시 장애 시 DB 직접 조회 폴백 |
| Canary 배포 중 v1 오류 | Alert rule으로 오류율 > 5% 감지 시 rollback 스크립트 즉시 실행 |
| Prometheus 메트릭 엔드포인트 외부 노출 | `/metrics/` IP 화이트리스트 설정 (Docker 내부 네트워크만 허용) |
| `@cache_page`와 JWT 인증 충돌 | `@cache_page`는 비인증 엔드포인트(목록 조회)에만 적용, 인증 필요 View 제외 |
| pg_stat_statements 성능 오버헤드 | `pg_stat_statements.max = 10000` 제한, 운영 환경에서 영향 미미 수준 |
| Cache invalidation 과잉 발생 | Signal은 `post_save`/`post_delete`에만 연결, 변경 빈도 낮은 목록 API에 집중 |

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-03-09 | 초기 Design 문서 작성 — Phase 5 Production Hardening | Frontend Architect |
