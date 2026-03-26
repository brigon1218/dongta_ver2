# Production 배포 및 Go-Live 상세 설계서

**Project**: dongta.com 마이그레이션 Production Deployment
**Date**: 2026-03-26
**Status**: Design Phase
**Reference Plan**: docs/01-plan/features/Production_배포_및_Go-Live.plan.md

---

## 📋 Design Overview

Plan 문서의 배포 목표를 달성하기 위한 상세 설계 및 구현 방안입니다.

---

## 🏗️ Phase 1: Pre-Deployment Setup (상세 절차)

### 1.1 AWS 환경 최종 설정

**대상 인스턴스**:
```
- Instance ID: dongta-prod-01
- IP: 52.79.148.197
- OS: Ubuntu 20.04 LTS
- Type: t3.xlarge (4 vCPU, 16GB RAM)
- Storage: 100GB EBS gp3
```

**Security Group 규칙** (설정할 것):
```
Inbound:
- SSH (22): 0.0.0.0/0 또는 특정 IP 제한
- HTTP (80): 0.0.0.0/0
- HTTPS (443): 0.0.0.0/0
- Prometheus (9090): 127.0.0.1:9090 (로컬 터널)

Outbound:
- All traffic to 0.0.0.0/0 (기본)
```

**필수 패키지 설치**:
```bash
#!/bin/bash
# Production 서버 초기화 스크립트

cd /home/ubuntu/work_01/dongta-django

# 1. 시스템 업데이트
sudo apt-get update && sudo apt-get upgrade -y

# 2. Docker & Docker Compose 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

docker --version
docker-compose --version

# 3. Python 및 필요 도구
sudo apt-get install -y \
  python3.10 \
  python3-pip \
  git \
  curl \
  wget \
  htop \
  tmux

# 4. 디렉토리 구조
mkdir -p /home/ubuntu/work_01/{logs,backups,data}
chmod 755 /home/ubuntu/work_01/logs
chmod 755 /home/ubuntu/work_01/backups
```

### 1.2 PostgreSQL 준비

**데이터베이스 마이그레이션** (MySQL → PostgreSQL):
```bash
#!/bin/bash
# db_migrate.sh - 데이터베이스 마이그레이션

# 1. Production DB 백업
BACKUP_FILE="dongta_prod_$(date +%Y%m%d_%H%M%S).sql"
cd /home/ubuntu/work_01/dongta-django

docker-compose -f docker-compose.staging.yml exec -T db \
  pg_dump -U dongta_user dongtadb_test > /home/ubuntu/work_01/backups/$BACKUP_FILE

echo "✅ Production DB backed up: $BACKUP_FILE"

# 2. 데이터 마이그레이션 (기존 MySQL에서)
# 이미 작성된 sync task 활용
docker-compose -f docker-compose.staging.yml exec -T web \
  python manage.py migrate

# 3. 정적 파일 수집
docker-compose -f docker-compose.staging.yml exec -T web \
  python manage.py collectstatic --noinput

echo "✅ Database migration completed"
```

### 1.3 SSL 인증서 설정

**Let's Encrypt / Cloudflare SSL** (기존 설정 활용):
```bash
# Cloudflare에서 제공하는 SSL 인증서를 사용하는 경우
# 1. Cloudflare Origin Certificate 다운로드
# 2. Nginx에 설치

mkdir -p /home/ubuntu/work_01/dongta-django/nginx/certs

# origin.crt와 private.key를 다음 위치에 배치:
# /home/ubuntu/work_01/dongta-django/nginx/certs/origin.crt
# /home/ubuntu/work_01/dongta-django/nginx/certs/private.key

# 권한 설정
chmod 600 /home/ubuntu/work_01/dongta-django/nginx/certs/*
```

**Nginx SSL 설정** (기존 파일 업데이트):
```nginx
# nginx/nginx.conf - SSL 구간 예시

server {
    listen 443 ssl http2;
    server_name dongta.theuit.info;

    ssl_certificate /etc/nginx/certs/origin.crt;
    ssl_certificate_key /etc/nginx/certs/private.key;

    # SSL 보안 설정
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # HSTS (선택)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # 리버스 프록시 설정
    location / {
        proxy_pass http://django_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTP → HTTPS 리다이렉트
server {
    listen 80;
    server_name dongta.theuit.info;
    return 301 https://$server_name$request_uri;
}
```

---

## 🚀 Phase 2: Docker Image & Deployment

### 2.1 Docker 이미지 빌드

**Dockerfile (기존 확인)** - 최적화 필요 항목:
```dockerfile
# dongta-django/Dockerfile

FROM python:3.10-slim

WORKDIR /app

# 의존성 설치
COPY requirements /app/requirements
RUN pip install --no-cache-dir -r requirements/production.txt

# 코드 복사
COPY . /app

# 정적 파일 수집
RUN python manage.py collectstatic --noinput

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python manage.py shell < /dev/null || exit 1

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "gthread", \
     "--threads", "2", \
     "--timeout", "60", \
     "--max-requests", "1000"]
```

**빌드 & 푸시**:
```bash
#!/bin/bash
# build_production_image.sh

cd /Volumes/sk-p31/workspace/vibe_coding/work_01/dongta-django

# 1. Docker 이미지 빌드
docker build -t dongta-django:prod-v1 .

# 2. 태그 추가 (선택: Docker Hub/ECR)
# docker tag dongta-django:prod-v1 your-registry/dongta-django:prod-v1
# docker push your-registry/dongta-django:prod-v1

echo "✅ Docker image built: dongta-django:prod-v1"

# 3. 이미지 검증
docker run --rm dongta-django:prod-v1 python manage.py --version
```

### 2.2 Production docker-compose.prod.yml

**작성할 파일**:
```yaml
# dongta-django/docker-compose.prod.yml
version: '3.9'

x-common: &common
  image: dongta-django:prod-v1
  restart: always
  env_file:
    - .env.production
  depends_on:
    db:
      condition: service_healthy
    redis:
      condition: service_healthy
  networks:
    - production

services:
  # PostgreSQL - Production
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: ${DB_USER:-dongta}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: dongtadb_prod
    volumes:
      - postgres_prod_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dongta"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - production
    restart: always

  # Redis - Production
  redis:
    image: redis:7-alpine
    command: redis-server --save 60 1 --loglevel warning
    volumes:
      - redis_prod_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - production
    restart: always

  # Django Web Service
  web:
    <<: *common
    container_name: dongta-web-prod
    command: gunicorn config.wsgi:application
      --bind 0.0.0.0:8000
      --workers 4
      --threads 2
      --worker-class gthread
      --timeout 60
      --max-requests 1000
      --access-logfile -
      --error-logfile -
    expose:
      - "8000"
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  # Celery Worker - Sync
  celery-sync:
    <<: *common
    container_name: dongta-celery-sync-prod
    command: celery -A config worker -l info -Q sync -c 2 --max-tasks-per-child 100

  # Celery Worker - Payment
  celery-payment:
    <<: *common
    container_name: dongta-celery-payment-prod
    command: celery -A config worker -l info -Q payment -c 2

  # Celery Beat - Scheduler
  celery-beat:
    <<: *common
    container_name: dongta-celery-beat-prod
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

  # Nginx - Reverse Proxy
  nginx:
    image: nginx:stable-alpine
    container_name: dongta-nginx-prod
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./nginx/certs:/etc/nginx/certs:ro
      - prod_static_volume:/app/staticfiles:ro
      - prod_media_volume:/app/media:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - web
    networks:
      - production
    restart: always

  # Prometheus - Metrics
  prometheus:
    image: prom/prometheus:latest
    container_name: dongta-prometheus-prod
    volumes:
      - ../config/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ../config/prometheus/alert_rules.yml:/etc/prometheus/alert_rules.yml:ro
      - prometheus_prod_data:/prometheus
    ports:
      - "127.0.0.1:9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    depends_on:
      - web
    networks:
      - production
    restart: always

  # Grafana - Dashboard
  grafana:
    image: grafana/grafana:latest
    container_name: dongta-grafana-prod
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
      GF_INSTALL_PLUGINS: redis-datasource
    volumes:
      - grafana_prod_data:/var/lib/grafana
    depends_on:
      - prometheus
    networks:
      - production
    restart: always

  # AlertManager - Alert Routing
  alertmanager:
    image: prom/alertmanager:latest
    container_name: dongta-alertmanager-prod
    volumes:
      - ../config/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    ports:
      - "127.0.0.1:9093:9093"
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    depends_on:
      - prometheus
    networks:
      - production
    restart: always

volumes:
  postgres_prod_data:
  redis_prod_data:
  prod_static_volume:
  prod_media_volume:
  prometheus_prod_data:
  grafana_prod_data:

networks:
  production:
    driver: bridge
```

---

## 📊 Phase 3: Canary Deployment Strategy

### 3.1 Nginx Upstream 설정

```nginx
# nginx/conf.d/upstream.conf

# Stable (기존) 버전
upstream django_stable {
    server web-stable:8000 weight=1 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

# Canary (신규) 버전
upstream django_canary {
    server web-canary:8000 weight=1 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

# 가중치 기반 라우팅 (기본: 100% stable)
upstream django_backend {
    server web-stable:8000 weight=99 max_fails=3 fail_timeout=30s;
    server web-canary:8000 weight=1 max_fails=3 fail_timeout=30s;
    keepalive 32;
}
```

### 3.2 자동 Canary 배포 스크립트

**deploy/production-canary-deploy.sh**:
```bash
#!/bin/bash
set -e

# Production Canary Deployment Script
# 사용: ./production-canary-deploy.sh

NAMESPACE="production"
STABLE_VERSION="v1"
CANARY_VERSION="v2"
PROMETHEUS_URL="http://localhost:9090"
ALERT_CHANNEL="slack"  # 또는 email

# Phase 1: 10% 트래픽 (2분 모니터링)
echo "🚀 Phase 1: Canary 10% traffic"
update_nginx_weight 99 1  # 99% stable, 1% canary
sleep 120

if check_metrics 0.01 1.0; then
    echo "✅ Phase 1 passed"
else
    echo "❌ Phase 1 failed - Rollback"
    rollback_to_stable
    exit 1
fi

# Phase 2: 50% 트래픽 (2분 모니터링)
echo "🚀 Phase 2: Canary 50% traffic"
update_nginx_weight 50 50  # 50% stable, 50% canary
sleep 120

if check_metrics 0.01 1.0; then
    echo "✅ Phase 2 passed"
else
    echo "❌ Phase 2 failed - Rollback"
    rollback_to_stable
    exit 1
fi

# Phase 3: 100% 트래픽
echo "🚀 Phase 3: Canary 100% traffic"
update_nginx_weight 0 100  # 100% canary
sleep 60

if check_metrics 0.01 1.0; then
    echo "✅ Phase 3 passed - Deployment complete!"
    promote_canary_to_stable
else
    echo "❌ Phase 3 failed - Rollback"
    rollback_to_stable
    exit 1
fi

# 함수 정의
update_nginx_weight() {
    local stable=$1
    local canary=$2
    # Nginx 설정 업데이트 후 reload
    sed -i "s/weight=[0-9]\+;/weight=$stable;/g" nginx/conf.d/upstream.conf
    docker exec dongta-nginx-prod nginx -s reload
    echo "Updated weights: stable=$stable%, canary=$canary%"
}

check_metrics() {
    local error_rate_threshold=$1
    local response_time_threshold=$2

    # Prometheus에서 메트릭 조회
    ERROR_RATE=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=rate(http_requests_total%5B5m%5D)" | jq '.' )

    # 간단한 체크 (실제로는 더 복잡한 로직)
    if [[ $(echo "$ERROR_RATE < $error_rate_threshold" | bc) -eq 1 ]]; then
        return 0
    else
        return 1
    fi
}

rollback_to_stable() {
    echo "⏮️  Rolling back to stable version..."
    update_nginx_weight 100 0
    echo "Rollback completed"
}

promote_canary_to_stable() {
    echo "✨ Promoting canary to stable..."
    docker tag dongta-django:canary-$CANARY_VERSION dongta-django:stable-$STABLE_VERSION
    echo "Promotion completed"
}
```

---

## 🔄 Phase 4: DNS Cutover & Go-Live

### 4.1 DNS 변경 계획

**타이밍**:
- TTL을 30초로 사전 변경 (배포 2시간 전)
- 트래픽 스위칭 (실제 배포 완료 후)

**변경 순서**:
```
1. Cloudflare DNS TTL: 3600초 → 30초
2. 30초 대기 (캐시 만료)
3. DNS A Record: 이전 PHP IP → 새 Django IP (52.79.148.197)
4. 트래픽 모니터링 (5-10분)
5. TTL 복구: 30초 → 3600초
```

### 4.2 Failover 계획 (5분 이내)

**만약 배포 실패 시**:
```
1. 에러율 > 5% 감지 (자동)
2. AlertManager → Slack 알림
3. Nginx canary 가중치 0으로 설정
4. 기존 PHP 서버로 DNS 즉시 복구
5. 문제 분석 후 재배포
```

---

## 📈 Phase 5: Monitoring & Alerting

### 5.1 주요 모니터링 지표

**Prometheus 쿼리**:
```promql
# 1. 에러율
rate(http_requests_total{status=~"5.."}[5m])

# 2. 응답 시간 (p95)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# 3. 캐시 hit rate
cache_hit_ratio

# 4. DB 연결 수
pg_stat_activity_count

# 5. CPU 사용률
node_cpu_usage_percent

# 6. 메모리 사용률
node_memory_usage_percent
```

### 5.2 Alert Rules (Production)

```yaml
# config/prometheus/alert_rules_production.yml
groups:
  - name: production_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 2m
        annotations:
          summary: "High error rate (>5%)"
          description: "Error rate is {{ $value | humanizePercentage }}"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5
        for: 5m
        annotations:
          summary: "High latency detected"

      - alert: DatabaseDown
        expr: pg_up == 0
        for: 1m
        annotations:
          summary: "PostgreSQL is down"

      - alert: LowCacheHitRate
        expr: cache_hit_ratio < 0.60
        for: 10m
        annotations:
          summary: "Cache hit rate is low (< 60%)"
```

---

## ✅ Validation Checklist

### Pre-Deployment
- [ ] AWS 보안 그룹 설정 완료
- [ ] PostgreSQL 백업 검증
- [ ] SSL 인증서 설치 확인
- [ ] Environment variables 검증
- [ ] Docker 이미지 빌드 성공
- [ ] Health check 엔드포인트 응답 확인

### During Deployment
- [ ] Canary Phase 1 (10%) 통과
- [ ] Canary Phase 2 (50%) 통과
- [ ] Canary Phase 3 (100%) 통과
- [ ] Prometheus 메트릭 수집 정상
- [ ] Grafana 대시보드 표시 정상

### Post-Deployment
- [ ] 모든 API 엔드포인트 응답 확인
- [ ] 사용자 로그인 기능 테스트
- [ ] 데이터 무결성 검증
- [ ] 모니터링 알림 정상 작동
- [ ] 성능 기준선 기록

---

## 🔧 구현 순서

1. **Step 1**: AWS 환경 설정 (30분)
2. **Step 2**: PostgreSQL 마이그레이션 (30분)
3. **Step 3**: SSL 인증서 설정 (15분)
4. **Step 4**: Docker 이미지 빌드 (20분)
5. **Step 5**: docker-compose.prod.yml 배포 (15분)
6. **Step 6**: Canary deployment (10분)
7. **Step 7**: DNS cutover (5분)
8. **Step 8**: 모니터링 & 검증 (30분)

**총 소요 시간**: ~3시간

---

## 📞 Runbook References

- **Emergency Response**: docs/deployment/emergency-response.md (작성 필요)
- **Rollback Procedure**: docs/deployment/rollback.md (작성 필요)
- **Incident Response**: docs/deployment/incident-response.md (작성 필요)

---

**설계 완료**: 2026-03-26
**상태**: ✅ Design 단계 완료
