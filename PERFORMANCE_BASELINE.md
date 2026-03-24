# 📊 성능 모니터링 기준선 (Performance Baseline)

**수집 일시**: 2026-03-11 22:44 UTC
**서버 환경**: AWS EC2 (2vCPU, 4GB RAM)
**부하 상태**: Idle (배포 직후)
**측정 방식**: `docker stats --no-stream`

---

## 📈 현재 성능 기준선

### 컨테이너별 리소스 사용률

```
┌────────────────────────────┬────────┬──────────────┬────────┐
│ Container                  │ CPU %  │ MEM Usage    │ MEM %  │
├────────────────────────────┼────────┼──────────────┼────────┤
│ dongta-django-web-1        │ 1.14%  │ 117.2 MiB    │ 3.06%  │  ← Django
│ dongta-django-db-1         │ 0.12%  │ 136.4 MiB    │ 3.56%  │  ← PostgreSQL
│ dongta-django-redis-1      │ 0.00%  │  73.53 MiB   │ 1.92%  │  ← Redis
│ dongta-django-celery-*-1   │ 0.24%  │ 136.7 MiB    │ 3.56%  │  ← Celery Payment
│ dongta-django-celery-*-2   │ 0.21%  │  94.3 MiB    │ 2.46%  │  ← Celery Sync-2
│ dongta-django-celery-*-3   │ 0.01%  │  24.68 MiB   │ 0.64%  │  ← Celery Beat
│ Nginx (Host)               │ 0.54%  │   3.523 MiB  │ 0.09%  │  ← Reverse Proxy
├────────────────────────────┼────────┼──────────────┼────────┤
│ TOTAL                      │ ~2.5%  │  ~586 MiB    │ ~15%   │
└────────────────────────────┴────────┴──────────────┴────────┘
```

### 📊 리소스 사용 현황

| 리소스 | 현재 사용 | 할당량 | 여유 | 평가 |
|--------|---------|--------|------|------|
| **CPU** | 2.5% | 200% (2vCPU) | 197.5% | ✅ 매우 여유 있음 |
| **메모리** | 586 MiB | 3,744 MiB | 3,158 MiB | ✅ 매우 여유 있음 |

---

## 🎯 성능 목표 (SLA)

### 기준선 설정 (Idle 상태)

```
✅ CPU Usage:         < 5% (현재 2.5%)
✅ Memory Usage:      < 50% (현재 15.6%)
✅ Container Count:   7 (healthy)
✅ Response Time:     < 200ms (p95)
✅ Error Rate:        < 0.1%
```

### 경고 임계값 (Alert Threshold)

```
⚠️  CPU > 30%        → 조사 필요
🔴 CPU > 50%        → 장애 상황
⚠️  Memory > 70%    → 조사 필요
🔴 Memory > 85%    → 장애 상황
⚠️  Response > 500ms → 조사 필요
🔴 Response > 1s    → 장애 상황
```

---

## 📋 모니터링 체크리스트

### 주간 모니터링 항목

| 항목 | 측정 방법 | 목표 | 현재 | 상태 |
|------|---------|------|------|------|
| **평균 CPU** | `docker stats` | < 10% | 2.5% | ✅ |
| **피크 CPU** | 업무시간 최대값 | < 30% | TBD | 🔄 |
| **평균 메모리** | `docker stats` | < 40% | 15.6% | ✅ |
| **피크 메모리** | 업무시간 최대값 | < 60% | TBD | 🔄 |
| **응답 시간 p50** | APM 도구 | < 100ms | TBD | 🔄 |
| **응답 시간 p95** | APM 도구 | < 200ms | TBD | 🔄 |
| **응답 시간 p99** | APM 도구 | < 500ms | TBD | 🔄 |
| **에러율** | 로그 분석 | < 0.1% | TBD | 🔄 |
| **DB 커넥션** | PostgreSQL stats | < 20 | TBD | 🔄 |
| **Redis 메모리** | Redis info | < 200MB | 73MB | ✅ |

---

## 🔧 모니터링 도구 설정

### Option 1: 간단한 Shell 모니터링 (지금 사용)

```bash
#!/bin/bash
# /home/ubuntu/work_01/monitor.sh

echo "Timestamp: $(date)"
echo "Docker Stats:"
docker stats --no-stream --format 'table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'

echo ""
echo "Disk Usage:"
df -h | grep -E '^/dev|Mounted'

echo ""
echo "Django Requests (last hour):"
docker-compose logs web | grep "GET\|POST" | tail -5
```

**실행**:
```bash
# 매 시간마다
*/1 * * * * /home/ubuntu/work_01/monitor.sh >> /var/log/dongta-monitor.log
```

### Option 2: Prometheus + Grafana (권장, 추후)

```yaml
# docker-compose-monitoring.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## 📅 1주일 모니터링 계획

### Day 1-7: 기준선 수립

**매일 09:00, 12:00, 15:00, 18:00 측정**

```
구간         | 예상 부하 | 측정 항목
─────────────┼─────────┼──────────────
09:00-10:00  | High    | CPU, Memory, Response Time
10:00-12:00  | Medium  | CPU, Memory, Error Rate
12:00-13:00  | Medium  | CPU, Memory, DB Connections
13:00-15:00  | High    | CPU, Memory, Response Time
15:00-18:00  | Medium  | CPU, Memory, Throughput
18:00+       | Low     | CPU, Memory, Storage
```

### 결과 분석 기준

| 측정값 | Pass 조건 | Fail 조건 |
|--------|----------|----------|
| 피크 CPU | < 30% | > 50% |
| 피크 메모리 | < 60% | > 80% |
| p95 응답시간 | < 200ms | > 500ms |
| 에러율 | < 0.1% | > 1% |

---

## 🚀 실행 단계

### Step 1: 모니터링 스크립트 배포 (NOW)

```bash
ssh ubuntu@52.79.148.197 'cat > /home/ubuntu/monitor.sh << "EOF"
#!/bin/bash
cd /home/ubuntu/work_01/dongta-django/dongta-django
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "Docker Container Stats:"
docker stats --no-stream --format 'table {{.Container}}\t{{.Names}}\t{{.CPUPerc}}\t{{.MemUsage}}'
echo ""
EOF
chmod +x /home/ubuntu/monitor.sh
'
```

### Step 2: 정기 모니터링 설정 (Cron)

```bash
ssh ubuntu@52.79.148.197 '
# 매 30분마다 모니터링 실행
(crontab -l 2>/dev/null; echo "*/30 * * * * /home/ubuntu/monitor.sh >> /tmp/dongta-monitor.log") | crontab -
'
```

### Step 3: 로그 수집 및 분석 (Weekly)

```bash
# 매주 월요일 09:00에 분석 보고서 생성
0 9 * * 1 /home/ubuntu/analyze-monitoring.sh
```

---

## 📊 성능 예측 (이론적 계산)

### 현재 기준선 (Idle)
```
CPU:     2.5%
Memory:  15.6%
```

### 예상 피크 시 (300명, 동시 30명)
```
CPU:     2.5% × 12 = ~30% (12배 부하로 추정)
Memory:  15.6% × 2 = ~31% (1.5-2배 증가)
```

**결론**: 여유 있음 ✅

---

## ✅ 성능 모니터링 체크리스트

- [x] 현재 성능 기준선 수립
- [x] 리소스 사용 현황 파악
- [x] 경고 임계값 설정
- [ ] 모니터링 스크립트 배포 (Next)
- [ ] Cron 작업 설정 (Next)
- [ ] 1주일 모니터링 수행 (Next)
- [ ] 분석 및 보고서 작성 (Next)

---

**최종 평가**: 🟢 **Docker 유지 결정 확정**
- CPU 사용률: 2.5% (매우 여유)
- 메모리 사용률: 15.6% (충분)
- 확장성: Docker 이점 명확

**다음 단계**: API 통합 테스트 진행 → 실제 부하 측정
