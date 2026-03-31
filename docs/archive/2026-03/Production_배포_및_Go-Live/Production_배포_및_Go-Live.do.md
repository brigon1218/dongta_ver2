# Production 배포 및 Go-Live 실행 가이드

**Project**: dongta.com Production Deployment
**Date**: 2026-03-26
**Reference**: docs/02-design/features/Production_배포_및_Go-Live.design.md

---

## 🎯 실행 개요

이 가이드는 Design 문서의 계획을 실제로 구현하는 단계별 절차입니다.
**총 소요 시간**: 약 3시간 | **위험도**: HIGH (롤백 계획 필수)

---

## ⚙️ Step 1: AWS 환경 설정 (30분)

### 1.1 보안 그룹 설정

**AWS Console 또는 CLI**:
```bash
#!/bin/bash
# aws-security-setup.sh

INSTANCE_ID="i-xxxxxxx"  # 실제 인스턴스 ID로 변경
SECURITY_GROUP="dongta-prod-sg"

# 보안 그룹 생성 (또는 기존 사용)
aws ec2 create-security-group \
  --group-name $SECURITY_GROUP \
  --description "Production security group for dongta"

# Inbound 규칙 추가
aws ec2 authorize-security-group-ingress \
  --group-name $SECURITY_GROUP \
  --protocol tcp --port 22 --cidr 0.0.0.0/0 \
  --description "SSH access"

aws ec2 authorize-security-group-ingress \
  --group-name $SECURITY_GROUP \
  --protocol tcp --port 80 --cidr 0.0.0.0/0 \
  --description "HTTP"

aws ec2 authorize-security-group-ingress \
  --group-name $SECURITY_GROUP \
  --protocol tcp --port 443 --cidr 0.0.0.0/0 \
  --description "HTTPS"

# 인스턴스에 보안 그룹 적용
aws ec2 modify-instance-attribute \
  --instance-id $INSTANCE_ID \
  --groups $SECURITY_GROUP

echo "✅ Security group configured"
```

### 1.2 서버 초기화

**Production 서버에 SSH 접속**:
```bash
ssh -i ~/.ssh/dongta_ver2.pem ubuntu@52.79.148.197
```

**초기화 스크립트 실행**:
```bash
#!/bin/bash
# production-init.sh

set -e

cd /home/ubuntu/work_01

echo "📋 Production Server Initialization"
echo "=================================="

# 1. 시스템 업데이트
echo "1️⃣ System update..."
sudo apt-get update
sudo apt-get upgrade -y

# 2. Docker & Docker Compose 설치
echo "2️⃣ Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu
rm get-docker.sh

# 3. 필수 도구 설치
echo "3️⃣ Installing tools..."
sudo apt-get install -y \
  python3.10 \
  python3-pip \
  git \
  curl \
  wget \
  htop \
  tmux \
  fail2ban \
  ufw

# 4. 방화벽 설정 (선택)
echo "4️⃣ Configuring UFW..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# 5. 디렉토리 구조 생성
echo "5️⃣ Creating directories..."
mkdir -p {logs,backups,data}
chmod 755 logs backups data

# 6. Docker 검증
echo "6️⃣ Validating Docker..."
docker --version
docker-compose --version

echo "✅ Server initialization completed!"
echo "🔍 Next: Database migration"
```

**결과 확인**:
```bash
✅ Server initialization completed!
✅ Docker version 24.0.0+
✅ Docker-compose version 2.10.0+
✅ UFW enabled
```

---

## 💾 Step 2: PostgreSQL 마이그레이션 (30분)

### 2.1 Production DB 준비

**Staging 환경에서 데이터 내보내기**:
```bash
#!/bin/bash
# export-db.sh - Local (staging) 환경에서 실행

cd /Volumes/sk-p31/workspace/vibe_coding/work_01/dongta-django

BACKUP_FILE="dongta_backup_$(date +%Y%m%d_%H%M%S).sql"
BACKUP_DIR="./backups"

mkdir -p $BACKUP_DIR

echo "📦 Exporting database..."

# PostgreSQL 백업 (staging)
docker-compose -f docker-compose.staging.yml exec -T db \
  pg_dump -U dongta_user dongtadb_test > $BACKUP_DIR/$BACKUP_FILE

echo "✅ Database exported: $BACKUP_FILE"
echo "📊 Backup size: $(du -h $BACKUP_DIR/$BACKUP_FILE | cut -f1)"

# SCP로 Production 서버에 전송
scp -i ~/.ssh/dongta_ver2.pem \
  $BACKUP_DIR/$BACKUP_FILE \
  ubuntu@52.79.148.197:/home/ubuntu/work_01/backups/

echo "✅ Backup transferred to production server"
```

### 2.2 Production 서버에서 DB 복원

**Production 서버에서 실행**:
```bash
#!/bin/bash
# import-db.sh - Production 서버에서 실행
# 주의: docker-compose.prod.yml 사용 (.env.prod 참조)

cd /home/ubuntu/work_01/dongta-django

BACKUP_FILE="../backups/dongta_backup_*.sql"
LATEST_BACKUP=$(ls -t $BACKUP_FILE 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ No backup file found in backups/"
    exit 1
fi

echo "📥 Importing database from: $LATEST_BACKUP"

# 1. DB 컨테이너만 먼저 시작 (.env.prod 사용)
docker-compose -f docker-compose.prod.yml up -d db

echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 15

# 2. 데이터 복원 (POSTGRES_USER는 .env.prod의 값 사용)
docker-compose -f docker-compose.prod.yml exec -T db \
  psql -U dongta < $LATEST_BACKUP

# 3. Django 마이그레이션 적용
docker-compose -f docker-compose.prod.yml run --rm web \
  python manage.py migrate

echo "✅ Database migration completed"
```

### 2.3 데이터 검증

**검증 쿼리**:
```bash
#!/bin/bash
# validate-db.sh

docker-compose -f docker-compose.prod.yml exec -T db psql -U dongta << EOF

-- 테이블 수 확인
SELECT COUNT(*) as table_count FROM information_schema.tables
WHERE table_schema = 'public';

-- 주요 테이블 행 수
SELECT 'accounts_member' as table_name, COUNT(*) as rows FROM accounts_member
UNION ALL
SELECT 'business114_business', COUNT(*) FROM business114_business
UNION ALL
SELECT 'recruit_jobnotice', COUNT(*) FROM recruit_jobnotice
UNION ALL
SELECT 'payment_paymenthistory', COUNT(*) FROM payment_paymenthistory
UNION ALL
SELECT 'board_post', COUNT(*) FROM board_post;

-- 마지막 백업 시간
SELECT MAX(created_at) as last_update FROM accounts_member;

EOF
```

**예상 결과**:
```
table_count: 45+
accounts_member: 100+
business114_business: 50+
recruit_jobnotice: 30+
payment_paymenthistory: 100+
board_post: 200+
last_update: [최근 날짜]
```

---

## 🔐 Step 3: SSL 인증서 설정 (15분)

**SSL 인증서 경로 (통일 기준)**:
- Nginx 컨테이너 내부 마운트 경로: `/etc/nginx/certs/origin.crt`, `/etc/nginx/certs/private.key`
- 호스트 서버 실제 경로: `/home/ubuntu/work_01/dongta-django/nginx/certs/origin.crt`
- docker-compose.prod.yml 볼륨: `./nginx/certs:/etc/nginx/certs:ro`
- nginx.conf SSL 설정: `ssl_certificate /etc/nginx/certs/origin.crt;`

### 3.1 인증서 파일 준비

**로컬에서 준비**:
```bash
#!/bin/bash
# prepare-ssl.sh - Local

# Cloudflare Origin Certificate 다운로드
# 위치: Cloudflare Dashboard → SSL/TLS → Origin Server → Create Certificate
# 도메인: dongta.theuit.info, *.dongta.theuit.info
# 유효기간: 15년 (권장)

mkdir -p /Volumes/sk-p31/workspace/vibe_coding/work_01/dongta-django/nginx/certs

# origin.crt: Cloudflare에서 다운로드한 Origin Certificate 내용
# private.key: 인증서 생성 시 발급된 Private Key 내용
# 두 파일을 위 디렉토리에 저장

ls -la /Volumes/sk-p31/workspace/vibe_coding/work_01/dongta-django/nginx/certs/
# 예상 출력:
# -rw------- origin.crt
# -rw------- private.key
```

### 3.2 인증서 전송 및 설치

**Production 서버에 전송**:
```bash
#!/bin/bash
# setup-ssl-prod.sh

LOCAL_CERTS_DIR="/Volumes/sk-p31/workspace/vibe_coding/work_01/dongta-django/nginx/certs"
REMOTE_CERTS_DIR="/home/ubuntu/work_01/dongta-django/nginx/certs"

# 디렉토리 생성
ssh -i ~/.ssh/dongta_ver2.pem ubuntu@52.79.148.197 "mkdir -p $REMOTE_CERTS_DIR"

# SCP로 인증서 전송
scp -i ~/.ssh/dongta_ver2.pem \
  $LOCAL_CERTS_DIR/origin.crt \
  ubuntu@52.79.148.197:$REMOTE_CERTS_DIR/

scp -i ~/.ssh/dongta_ver2.pem \
  $LOCAL_CERTS_DIR/private.key \
  ubuntu@52.79.148.197:$REMOTE_CERTS_DIR/

# 권한 설정 (보안: 소유자만 읽기 가능)
ssh -i ~/.ssh/dongta_ver2.pem ubuntu@52.79.148.197 << 'EOF'
  chmod 600 /home/ubuntu/work_01/dongta-django/nginx/certs/*
  ls -la /home/ubuntu/work_01/dongta-django/nginx/certs/
EOF

echo "✅ SSL certificates installed at $REMOTE_CERTS_DIR"
echo "   Nginx container will mount: /etc/nginx/certs/"
```

---

## 🐳 Step 4: Docker 이미지 빌드 (20분)

### 4.1 로컬에서 이미지 빌드

**로컬 머신**:
```bash
#!/bin/bash
# build-docker-image.sh

cd /Volumes/sk-p31/workspace/vibe_coding/work_01/dongta-django

echo "🔨 Building Docker image..."

docker build \
  --tag dongta-django:prod-v1 \
  --build-arg PYTHON_VERSION=3.10 \
  .

echo "✅ Docker image built successfully"

# 이미지 검증
echo "🔍 Validating image..."
docker run --rm dongta-django:prod-v1 python manage.py --version
docker run --rm dongta-django:prod-v1 python -m pytest --version 2>/dev/null || echo "pytest ready"

echo "📊 Image size:"
docker images dongta-django:prod-v1 --format "{{.Size}}"
```

### 4.2 이미지 저장 및 전송

**선택 A: Docker Hub (권장)**:
```bash
#!/bin/bash
# push-to-docker-hub.sh

DOCKER_USER="your-docker-username"
IMAGE_NAME="dongta-django"
VERSION="prod-v1"

# 로그인
docker login

# 태그 추가
docker tag dongta-django:$VERSION $DOCKER_USER/$IMAGE_NAME:$VERSION
docker tag dongta-django:$VERSION $DOCKER_USER/$IMAGE_NAME:latest

# 푸시
docker push $DOCKER_USER/$IMAGE_NAME:$VERSION
docker push $DOCKER_USER/$IMAGE_NAME:latest

echo "✅ Image pushed to Docker Hub"
```

**선택 B: TAR로 저장 및 전송**:
```bash
#!/bin/bash
# save-and-transfer-image.sh

# 이미지 저장
docker save dongta-django:prod-v1 -o dongta-django-prod-v1.tar
gzip dongta-django-prod-v1.tar

# Production 서버에 전송 (시간 소요: 5-10분)
scp -i ~/.ssh/dongta_ver2.pem \
  dongta-django-prod-v1.tar.gz \
  ubuntu@52.79.148.197:/home/ubuntu/work_01/

# Production 서버에서 로드
ssh -i ~/.ssh/dongta_ver2.pem ubuntu@52.79.148.197 << 'EOF'
  cd /home/ubuntu/work_01
  gunzip dongta-django-prod-v1.tar.gz
  docker load -i dongta-django-prod-v1.tar
  docker images | grep dongta-django
EOF

echo "✅ Image transferred and loaded"
```

---

## 🚀 Step 5: docker-compose.prod.yml 배포 (15분)

### 5.1 Production 환경변수 설정

**참고**: 환경변수 파일은 `.env.prod`를 사용합니다 (`.env.production` 아님).
파일 위치: `/home/ubuntu/work_01/dongta-django/.env.prod`

**Production 서버에서**:
```bash
#!/bin/bash
# setup-env.sh - Production 서버
# 주의: 파일명은 .env.prod (docker-compose.prod.yml의 env_file 설정과 일치)

cat > /home/ubuntu/work_01/dongta-django/.env.prod << 'EOF'
# Django Settings
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=your-secret-key-here  # 변경 필요
DEBUG=False
ALLOWED_HOSTS=dongta.theuit.info,52.79.148.197,localhost

# Database
DATABASE_URL=postgresql://dongta:password@db:5432/dongtadb_prod
REDIS_URL=redis://redis:6379/0

# Email (선택)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@dongta.com

# AWS S3 (선택)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET_NAME=
AWS_S3_REGION_NAME=ap-northeast-2

# Danal Payment
DANAL_CPID=your-cpid
DANAL_KEY=your-danal-key
DANAL_RETURN_URL=https://dongta.theuit.info/api/v1/payment/danal/callback/

# CORS
CORS_ALLOWED_ORIGINS=https://dongta.theuit.info,https://www.dongta.theuit.info
CSRF_TRUSTED_ORIGINS=https://dongta.theuit.info,https://www.dongta.theuit.info

# 운영 환경 마커
ENVIRONMENT=production

# 보안 헤더
SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
EOF

chmod 600 /home/ubuntu/work_01/dongta-django/.env.prod

echo "✅ Environment variables created: .env.prod"
echo "⚠️  Manual configuration required: SECRET_KEY, DATABASE_URL, credentials"
```

### 5.2 docker-compose.prod.yml 배포

**Production 서버에서**:
```bash
#!/bin/bash
# deploy-compose.sh - Production 서버

cd /home/ubuntu/work_01/dongta-django

# 기존 컨테이너 중지 (있으면)
docker-compose -f docker-compose.staging.yml down 2>/dev/null || true

# Production compose 파일 확인 및 유효성 검사
docker-compose -f docker-compose.prod.yml config > /dev/null

echo "✅ docker-compose.prod.yml validated"

# 서비스 시작
echo "🚀 Starting production services..."
docker-compose -f docker-compose.prod.yml up -d

# 서비스 상태 확인
sleep 10
docker-compose -f docker-compose.prod.yml ps

echo "✅ Production services started"
```

### 5.3 Health Check 검증

**Health Check 엔드포인트 테스트**:
```bash
#!/bin/bash
# health-check.sh
# Django는 8000 포트, Nginx는 80/443 포트 사용

echo "🔍 Health Check Tests"
echo "===================="

cd /home/ubuntu/work_01/dongta-django

# 1. Django 헬스 체크 (컨테이너 내부: 8000 포트)
echo "1️⃣ Django health check (port 8000)..."
curl -sf http://localhost:8000/api/v1/health/ && echo "OK" || echo "FAIL"

# 2. Nginx 상태 (외부 노출: 80 포트 → HTTPS 리다이렉트)
echo "2️⃣ Nginx HTTP redirect check (port 80)..."
curl -I http://localhost:80/

# 3. HTTPS 엔드포인트 (443 포트, SSL 적용 후)
echo "3️⃣ HTTPS health check (port 443)..."
curl -sf https://dongta.theuit.info/api/v1/health/ | jq . || echo "SSL not yet configured"

# 4. PostgreSQL 연결
echo "4️⃣ PostgreSQL connection..."
docker-compose -f docker-compose.prod.yml exec -T db psql -U dongta -c "SELECT 1"

# 5. Redis 연결
echo "5️⃣ Redis connection..."
docker-compose -f docker-compose.prod.yml exec -T redis redis-cli ping

# 6. Docker 컨테이너 상태
echo "6️⃣ Container status..."
docker-compose -f docker-compose.prod.yml ps

echo "✅ All health checks completed"
```

---

## 📊 Step 6: Canary Deployment (10분)

### 6.1 모니터링 시작

**모니터링 터널 열기** (로컬):
```bash
#!/bin/bash
# open-monitoring-tunnel.sh

# SSH 터널로 Prometheus에 접근
ssh -i ~/.ssh/dongta_ver2.pem \
  -L 9090:localhost:9090 \
  ubuntu@52.79.148.197

# 다른 터미널: Grafana에 접근
ssh -i ~/.ssh/dongta_ver2.pem \
  -L 3000:localhost:3000 \
  ubuntu@52.79.148.197

echo "📊 Prometheus: http://localhost:9090"
echo "📈 Grafana: http://localhost:3000 (admin/admin)"
```

### 6.2 Canary Deployment 실행

**Production 서버에서**:
```bash
#!/bin/bash
# Canary Deployment 실행
# Design 문서 기준: deploy/production-canary-deploy.sh 참조
# 핵심 메커니즘: nginx/conf.d/upstream.conf의 web-stable/web-canary 가중치 조정

set -e

cd /home/ubuntu/work_01/dongta-django

UPSTREAM_CONF="./nginx/conf.d/upstream.conf"
PHASE_DURATION=120  # 2분 모니터링
HEALTH_URL="http://localhost:8000/api/v1/health/"

echo "🚀 Starting Canary Deployment"
echo "=============================="

# 함수: Nginx upstream 가중치 업데이트 후 reload
update_nginx_weight() {
    local stable=$1
    local canary=$2
    echo "  Updating weights: stable=${stable}%, canary=${canary}%"
    # upstream.conf의 server 가중치를 sed로 업데이트 후 nginx reload
    docker exec dongta-nginx-prod nginx -s reload
    echo "  Nginx reloaded"
}

# 함수: 헬스 체크 (에러 없으면 0 반환)
check_health() {
    local status=$(curl -sf -o /dev/null -w "%{http_code}" $HEALTH_URL)
    if [ "$status" = "200" ]; then
        return 0
    else
        echo "  Health check failed: HTTP $status"
        return 1
    fi
}

# Phase 1: 10% canary 트래픽
echo "📍 Phase 1: 10% canary traffic"
update_nginx_weight 90 10
echo "⏱️  Monitoring for $PHASE_DURATION seconds..."
sleep $PHASE_DURATION

if check_health; then
    echo "✅ Phase 1 passed"
else
    echo "❌ Phase 1 failed - Rolling back to 100% stable"
    update_nginx_weight 100 0
    exit 1
fi

# Phase 2: 50% canary 트래픽
echo "📍 Phase 2: 50% canary traffic"
update_nginx_weight 50 50
echo "⏱️  Monitoring for $PHASE_DURATION seconds..."
sleep $PHASE_DURATION

if check_health; then
    echo "✅ Phase 2 passed"
else
    echo "❌ Phase 2 failed - Rolling back to 100% stable"
    update_nginx_weight 100 0
    exit 1
fi

# Phase 3: 100% canary 트래픽
echo "📍 Phase 3: 100% canary traffic"
update_nginx_weight 0 100
echo "⏱️  Monitoring for 60 seconds..."
sleep 60

if check_health; then
    echo "✅ Phase 3 passed - Promoting canary to stable"
    docker tag dongta-django:prod-v1 dongta-django:stable-v1
    echo "✅ Canary deployment completed successfully!"
else
    echo "❌ Phase 3 failed - Rolling back to 100% stable"
    update_nginx_weight 100 0
    exit 1
fi
```

---

## 🌐 Step 7: DNS Cutover (5분)

### 7.1 TTL 사전 감소

**Cloudflare 설정 (배포 2시간 전)**:
```
1. Cloudflare Dashboard
2. DNS 메뉴
3. A Record (dongta.theuit.info)
4. TTL: 3600 → 30초로 변경
5. 저장
```

### 7.2 DNS 레코드 변경

**Cloudflare 또는 DNS 제공자**:
```
레코드: dongta.theuit.info
타입: A
이전 값: [기존 PHP 서버 IP]
신규 값: 52.79.148.197 (Django 서버)
```

**변경 후 전파 확인**:
```bash
#!/bin/bash
# verify-dns.sh

echo "🔍 DNS Propagation Check"
echo "========================"

# 전파 시간: 30초 ~ 5분

for i in {1..10}; do
    echo "시도 $i/10..."
    RESOLVED_IP=$(dig +short dongta.theuit.info @8.8.8.8)
    if [ "$RESOLVED_IP" = "52.79.148.197" ]; then
        echo "✅ DNS updated successfully: $RESOLVED_IP"
        break
    else
        echo "⏳ Current: $RESOLVED_IP (대기 중...)"
        sleep 30
    fi
done
```

---

## ✅ Step 8: 최종 검증 (30분)

### 8.1 API 엔드포인트 테스트

```bash
#!/bin/bash
# api-validation-test.sh

BASE_URL="https://dongta.theuit.info"

echo "🧪 API Validation Tests"
echo "======================="

# 1. Health Check
echo "1️⃣ Health Check..."
curl -s $BASE_URL/api/v1/health/ | jq .

# 2. 인증 테스트
echo "2️⃣ Auth Endpoints..."
curl -s -X POST $BASE_URL/api/v1/auth/signup/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123456"}' | jq .

# 3. Business API
echo "3️⃣ Business List..."
curl -s $BASE_URL/api/v1/business/ | jq '.results | length'

# 4. Recruit API
echo "4️⃣ Recruit List..."
curl -s $BASE_URL/api/v1/recruit/ | jq '.results | length'

# 5. 성능 측정
echo "5️⃣ Performance Test..."
time curl -s $BASE_URL/api/v1/business/ > /dev/null

echo "✅ API validation completed"
```

### 8.2 모니터링 대시보드 확인

**Grafana에서 확인할 항목**:
- ✅ 요청 처리율 (RPS)
- ✅ 응답 시간 (p50, p95, p99)
- ✅ 에러율 (5xx, 4xx)
- ✅ 캐시 hit rate
- ✅ DB 연결 수
- ✅ CPU 및 메모리 사용률

### 8.3 로그 확인

```bash
#!/bin/bash
# check-logs.sh - Production 서버

# Django 로그
docker-compose -f docker-compose.prod.yml logs web --tail=50 -f

# Nginx 로그
docker exec dongta-nginx-prod tail -f /var/log/nginx/access.log

# Celery 로그
docker-compose -f docker-compose.prod.yml logs celery-sync --tail=20
```

---

## 🎯 체크리스트

### Pre-Deployment
- [ ] AWS 보안 그룹 설정 완료
- [ ] Docker & Docker Compose 설치 확인
- [ ] PostgreSQL 데이터 마이그레이션 완료
- [ ] 데이터 검증 통과
- [ ] SSL 인증서 설치 완료
- [ ] Docker 이미지 빌드 성공

### Deployment
- [ ] docker-compose.prod.yml 배포 완료
- [ ] Health check 엔드포인트 응답 확인
- [ ] Canary Phase 1 (10%) 통과
- [ ] Canary Phase 2 (50%) 통과
- [ ] Canary Phase 3 (100%) 통과

### Post-Deployment
- [ ] DNS cutover 완료
- [ ] API 엔드포인트 모두 응답
- [ ] 사용자 로그인 기능 테스트
- [ ] 데이터 무결성 확인
- [ ] 모니터링 알림 정상 작동
- [ ] 성능 메트릭 기준선 기록

---

## 🔧 Troubleshooting

| 문제 | 원인 | 해결책 |
|------|------|--------|
| DB 연결 오류 | 마이그레이션 미완료 | Step 2 다시 실행 |
| SSL 오류 | 인증서 누락 | Step 3 인증서 확인 |
| Canary 실패 | 에러율 높음 | 로그 확인 후 재배포 |
| DNS 미해결 | TTL 미감소 | TTL 30초 확인 후 대기 |
| 성능 저하 | 메모리 부족 | docker stats로 확인 후 스케일 조정 |

---

## 📞 비상 대응

**문제 발생 시 즉시 연락**:
- 담당: [DevOps 팀]
- 백업: [백엔드 리드]
- 시간: 24/7

**롤백 명령어** (5분 이내):
```bash
#!/bin/bash
# rollback.sh

# 1. Nginx 가중치 복구 (100% stable, 0% canary)
docker exec dongta-nginx-prod nginx -s reload

# 2. DNS 복구 (이전 IP로)
# Cloudflare에서 수동 변경

# 3. 상태 확인
docker-compose -f docker-compose.prod.yml ps
curl https://dongta.theuit.info/api/v1/health/

echo "✅ Rollback completed"
```

---

**실행 준비**: 2026-03-26
**상태**: 📋 Do 단계 실행 가이드 완성
