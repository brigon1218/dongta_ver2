"""
dongta 커스텀 Prometheus 메트릭 정의
- 요청 레이턴시 히스토그램
- DB 쿼리 카운트
- 캐시 히트율
- 카나리 트래픽 비율
"""
from prometheus_client import (
    Histogram,
    Counter,
    Gauge,
)

# 요청 레이턴시 히스토그램 (엔드포인트별)
REQUEST_LATENCY = Histogram(
    'dongta_request_latency_seconds',
    'HTTP request latency in seconds',
    labelnames=['method', 'endpoint', 'status_code'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# DB 쿼리 카운트 (뷰/액션별)
DB_QUERY_COUNT = Counter(
    'dongta_db_query_total',
    'Total number of DB queries executed',
    labelnames=['view', 'action'],
)

# 캐시 히트/미스 카운터
CACHE_HIT_COUNTER = Counter(
    'dongta_cache_hits_total',
    'Total number of cache hits',
    labelnames=['cache_name'],
)

CACHE_MISS_COUNTER = Counter(
    'dongta_cache_misses_total',
    'Total number of cache misses',
    labelnames=['cache_name'],
)

# 카나리 트래픽 비율 게이지 (0.0 ~ 1.0)
CANARY_TRAFFIC_RATIO = Gauge(
    'dongta_canary_traffic_ratio',
    'Current ratio of traffic routed to canary deployment (0.0 ~ 1.0)',
)


def record_request_latency(method: str, endpoint: str, status_code: int, duration: float):
    """요청 레이턴시 기록"""
    REQUEST_LATENCY.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
    ).observe(duration)


def record_db_queries(view: str, action: str, count: int = 1):
    """DB 쿼리 카운트 기록"""
    DB_QUERY_COUNT.labels(view=view, action=action).inc(count)


def record_cache_hit(cache_name: str = 'default'):
    """캐시 히트 기록"""
    CACHE_HIT_COUNTER.labels(cache_name=cache_name).inc()


def record_cache_miss(cache_name: str = 'default'):
    """캐시 미스 기록"""
    CACHE_MISS_COUNTER.labels(cache_name=cache_name).inc()


def set_canary_traffic_ratio(ratio: float):
    """카나리 트래픽 비율 설정 (0.0 ~ 1.0)"""
    CANARY_TRAFFIC_RATIO.set(max(0.0, min(1.0, ratio)))
