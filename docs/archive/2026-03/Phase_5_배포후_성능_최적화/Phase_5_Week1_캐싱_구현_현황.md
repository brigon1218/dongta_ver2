# Phase 5 - Week 1: View-level Caching 구현 현황

> **Date**: 2026-03-26
> **Status**: Implementation Complete
> **Match Rate**: Design과 일치도 확인 필요

---

## 1. 구현 완료 항목

### 1.1 Caching 적용

#### recruit/views.py
```python
✅ @method_decorator(cache_page(timeout=300))
   - JobNoticeViewSet.list() → 5분 캐시

✅ @method_decorator(cache_page(timeout=600))
   - JobNoticeViewSet.retrieve() → 10분 캐시
```

#### business114/views.py
```python
✅ @method_decorator(cache_page(timeout=300))
   - BusinessViewSet.list() → 5분 캐시

✅ @method_decorator(cache_page(timeout=600))
   - BusinessViewSet.retrieve() → 10분 캐시
   - 주의: 조회수 증가도 캐시되므로 추후 개선 필요
```

### 1.2 Signal 기반 캐시 무효화

#### apps/recruit/signals.py (신규)
```python
✅ post_save JobNotice → cache.delete() 목록/상세
✅ post_delete JobNotice → cache.delete() 목록/상세
✅ post_save Company → 회사 관련 공고 캐시 무효화
```

#### apps/business114/signals.py (신규)
```python
✅ post_save Business → cache.delete() 목록/상세
✅ post_delete Business → cache.delete() 목록/상세
```

#### apps.py 생성
```python
✅ apps/recruit/apps.py → Signal 등록
✅ apps/business114/apps.py → Signal 등록
```

### 1.3 Database 최적화

#### config/settings/base.py
```python
✅ CONN_MAX_AGE = 60초 (Connection Pooling)
✅ DB_CONNECT_TIMEOUT = 10초
✅ MySQL 레거시도 동일 설정 적용
```

### 1.4 Slow Query 로깅

#### config/settings/production.py
```python
✅ django.db.backends 로거 추가 (DEBUG 레벨)
✅ SLOW_QUERY_LOG_THRESHOLD_MS = 100 (환경변수)
```

---

## 2. 테스트 계획

### 2.1 Caching 검증
```bash
# Redis Monitor로 캐시 히트 확인
redis-cli MONITOR

# API 요청 2회 → 두 번째는 캐시된 응답
curl http://localhost:8000/api/v1/recruit/
curl http://localhost:8000/api/v1/recruit/
```

### 2.2 Signal 검증
```bash
# JobNotice 생성 → 캐시 무효화 확인
curl -X POST http://localhost:8000/api/v1/recruit/ \
  -H "Authorization: Bearer <token>" \
  -d '{"...": "..."}'

# Redis 모니터 확인 → DELETE 커맨드 확인
```

### 2.3 DB 성능 확인
```bash
# 현재 DB 연결 수 확인
SELECT count(*) FROM pg_stat_activity;

# Slow query 로그 확인
tail -f logs/django.log | grep "duration:"
```

---

## 3. 환경변수 설정

추가 필요한 .env 항목:
```bash
# Database
DB_CONN_MAX_AGE=60
DB_CONNECT_TIMEOUT=10

# Slow Query
SLOW_QUERY_LOG_THRESHOLD_MS=100

# Cache
CACHE_MIDDLEWARE_SECONDS=300
```

---

## 4. 다음 단계

### Week 2: Prometheus + Grafana (2026-03-27~03-28)
- [ ] django-prometheus 설치 및 설정
- [ ] Prometheus scrape 설정
- [ ] Grafana 대시보드 구성
- [ ] Alert rules 설정

---

## 5. 주요 주의사항

### 5.1 캐시 일관성
- 데이터 변경 시 Signal로 즉시 무효화
- URL 패턴 캐시는 `cache.delete()` 대신 Redis 패턴 매칭 필요
- 예: `cache.delete_many(['/api/v1/recruit/*'])`

### 5.2 조회수 문제 (business114)
- 현재: 조회수가 캐시되어 증가 안 됨
- 개선안:
  1. Celery Task로 비동기 처리
  2. 캐시 제외 (캐싱 안 함)
  3. Nginx cache에서 제외

### 5.3 개인화 데이터 캐싱 금지
- 프로필 API는 캐싱 제외 (개인 정보)
- 권한 변경 시 즉시 반영 필요

---

## 6. Performance Baseline (구현 전)

측정이 필요한 메트릭:
- [ ] P95 응답시간 (현재)
- [ ] Redis 히트율 (구현 후)
- [ ] DB 연결 수 변화
- [ ] CPU/Memory 사용률

```bash
# Baseline 측정 (K6 또는 Locust)
k6 run load-test.js --summary

# 결과:
# - Current P95: ???ms
# - Cache Hit: 0%
# - DB Connections: ???
```

---

## Version History

| Date | Changes | Author |
|------|---------|--------|
| 2026-03-26 | Week 1 캐싱 구현 완료 | Backend Team |
