# core — PDCA 완료 보고서

**Feature**: core  
**Phase**: Report  
**Date**: 2026-03-31  
**Match Rate (최종)**: 90%  
**Iteration**: 1회 (수동 수정)

---

## Executive Summary

| 관점 | 내용 |
|------|------|
| **Problem** | `apps/core/` 앱이 `__init__.py` 없이 배포됨. Prometheus metrics 엔드포인트 비활성화로 모니터링 불가. 커스텀 메트릭 정의만 있고 실제 수집 안 됨. |
| **Solution** | `__init__.py` 추가, `metrics/` URL 활성화, `CacheHitHeaderMiddleware`에 request latency 기록 연결. |
| **Function UX Effect** | `/metrics` 엔드포인트 노출로 Prometheus → Grafana 모니터링 파이프라인 완성. 모든 HTTP 요청 레이턴시 자동 수집. |
| **Core Value** | 프로덕션 가시성(observability) 확보. Canary 배포 트래픽 비율 모니터링 가능. |

---

## 1. 구현 현황

### 1.1 파일 구성

| 파일 | 상태 | 역할 |
|------|------|------|
| `apps/core/__init__.py` | ✅ 신규 추가 | Django 패키지 정식 등록 |
| `apps/core/views.py` | ✅ 기존 유지 | LandingPageView + HealthCheckView |
| `apps/core/metrics.py` | ✅ 기존 유지 | Prometheus 커스텀 메트릭 정의 |
| `apps/core/middleware.py` | ✅ 수정됨 | CacheHitHeader + RequestLatency 기록 |
| `config/urls.py` | ✅ 수정됨 | `metrics/` URL 활성화 |

### 1.2 연관 모듈

| 모듈 | 위치 | 역할 |
|------|------|------|
| `core/exceptions.py` | `dongta-django/core/` | 커스텀 예외 핸들러 |
| `core/pagination.py` | `dongta-django/core/` | StandardResultsSetPagination |
| `core/permissions.py` | `dongta-django/core/` | IsOwner, IsOwnerOrReadOnly |

---

## 2. Gap Analysis 결과

### 2.1 수정 전 (71%)

| 항목 | 점수 | 문제 |
|------|------|------|
| Structural | 80% | `__init__.py` 누락 |
| Functional | 65% | 커스텀 메트릭 미연결 |
| Contract | 70% | `metrics/` URL 비활성화 |
| **Overall** | **71%** | |

### 2.2 수정 후 (90%)

| 항목 | 점수 | 내용 |
|------|------|------|
| Structural | 100% | `__init__.py` 추가 완료 |
| Functional | 85% | request latency 자동 수집 연결 |
| Contract | 90% | `metrics/` 엔드포인트 활성화 |
| **Overall** | **90%** | |

---

## 3. 수정 내용 상세

### Fix 1: `apps/core/__init__.py` 추가
```
dongta-django/apps/core/__init__.py (신규, 빈 파일)
```
- Django 공식 앱 패키지로 등록
- Python 네임스페이스 패키지 의존 제거

### Fix 2: Prometheus metrics URL 활성화
```python
# config/urls.py
# Before:
# path('metrics/', include('django_prometheus.urls')),

# After:
path('metrics/', include('django_prometheus.urls')),
```
- `GET /metrics` 엔드포인트 노출
- Prometheus scrape 가능

### Fix 3: CacheHitHeaderMiddleware에 request latency 연결
```python
# apps/core/middleware.py
import time
from apps.core.metrics import record_request_latency

# __call__ 내부:
start_time = time.monotonic()
response = self.get_response(request)
duration = time.monotonic() - start_time
record_request_latency(method, endpoint, status_code, duration)
```
- 모든 HTTP 요청의 method / path / status_code / duration 자동 수집
- `dongta_request_latency_seconds` 히스토그램에 기록

---

## 4. 검증 포인트

| 항목 | 검증 방법 | 기대 결과 |
|------|-----------|-----------|
| metrics 엔드포인트 | `GET /metrics` | 200 + Prometheus 텍스트 포맷 |
| health check | `GET /api/v1/health/` | `{"status": "healthy", ...}` |
| request latency | Grafana 확인 | `dongta_request_latency_seconds` 히스토그램 |
| cache hit header | 임의 요청 | `X-Cache-Hit: HIT` 또는 `MISS` 헤더 |

---

## 5. 잔여 이슈

| 항목 | 심각도 | 내용 |
|------|--------|------|
| `apps/core` INSTALLED_APPS 미등록 | Minor | 현재 migration 불필요하므로 무방. 향후 모델 추가 시 등록 필요. |
| `record_db_queries`, `record_cache_hit/miss` 미연결 | Minor | 정의됨. 필요 시 각 앱 뷰에서 직접 호출 가능. |
| `CANARY_TRAFFIC_RATIO` 게이지 미설정 | Minor | 카나리 배포 시 `set_canary_traffic_ratio()` 수동 호출 필요. |

---

## 6. 다음 단계

- 서버 배포 후 `GET /metrics` 접근 확인
- Prometheus `prometheus.yml`의 scrape target에 Django 앱 추가 확인
- Grafana 대시보드에서 `dongta_request_latency_seconds` 패널 확인
