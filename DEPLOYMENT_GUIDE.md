# 🚀 dongta.com 배포 가이드

## 📋 배포 체크리스트

### Step 1: GitHub Secrets 설정 ✅

GitHub 저장소 Settings → Secrets and variables → Actions 에서 다음 환경변수를 추가합니다:

#### 🔐 필수 Secrets

| Key | Value | 설명 |
|-----|-------|------|
| `DOCKER_USERNAME` | Docker Hub 사용자명 | Docker 이미지 푸시용 |
| `DOCKER_PASSWORD` | Docker Hub 비밀번호 | Docker 이미지 푸시용 |
| `DEPLOY_HOST` | 운영 서버 IP/도메인 | SSH 배포 대상 |
| `DEPLOY_USER` | SSH 접속 사용자명 | 예: `ubuntu`, `ec2-user` |
| `DEPLOY_KEY` | SSH 비공개키 (PEM) | 서버 접속 인증 |
| `SECRET_KEY` | Django SECRET_KEY | 보안 임의값 생성 필수 |
| `DATABASE_URL` | PostgreSQL 연결 URL | `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | Redis 연결 URL | `redis://host:6379/0` |
| `MYSQL_DATABASE_URL` | MySQL 연결 URL (하이브리드) | `mysql://user:pass@host:3306/db` |
| `ALLOWED_HOSTS` | 허용할 호스트 | `dongta.theuit.info,www.dongta.theuit.info` |
| `SENTRY_DSN` | Sentry DSN URL | 오류 추적용 |
| `DANAL_CPID` | 다날 상점 ID | 결제 연동용 |
| `DANAL_KEY` | 다날 API 키 | 결제 연동용 |
| `AWS_ACCESS_KEY_ID` | AWS 액세스 키 | S3 파일 저장용 |
| `AWS_SECRET_ACCESS_KEY` | AWS 시크릿 키 | S3 파일 저장용 |
| `AWS_STORAGE_BUCKET_NAME` | S3 버킷명 | 예: `dongta-prod-uploads` |
| `AWS_S3_REGION_NAME` | AWS 리전 | 예: `ap-northeast-2` |
| `SLACK_WEBHOOK` | Slack Webhook URL | 배포 알림용 (선택사항) |

#### 🔧 GitHub Secrets 추가 방법

```bash
# 1. GitHub CLI를 사용한 방법 (권장)
gh secret set SECRET_KEY --body "your-secret-key-value"
gh secret set DATABASE_URL --body "postgresql://user:pass@host:5432/db"
# ... 반복

# 2. GitHub 웹 UI를 사용한 방법
# 저장소 → Settings → Secrets and variables → Actions → New repository secret
```

---

### Step 2: 운영 서버 준비 ✅

#### AWS EC2 인스턴스 설정

```bash
# 1. 서버 접속
ssh -i your-key.pem ubuntu@your-server-ip

# 2. 필수 패키지 설치
sudo apt update && sudo apt install -y \
    docker.io \
    docker-compose \
    git \
    curl \
    postgresql-client

# 3. Docker 그룹에 사용자 추가 (sudo 없이 docker 실행)
sudo usermod -aG docker ubuntu

# 4. 애플리케이션 디렉토리 생성
mkdir -p /app/dongta-django
cd /app/dongta-django

# 5. 로그 디렉토리 생성
sudo mkdir -p /var/log/django
sudo chown ubuntu:ubuntu /var/log/django

# 6. Git 저장소 초기화
git init
git remote add origin https://github.com/brigon1218/dongta_ver2.git
```

#### Nginx 설정 (리버스 프록시)

```bash
# 1. Nginx 설치
sudo apt install -y nginx

# 2. Nginx 설정 파일 생성
sudo nano /etc/nginx/sites-available/dongta

# 3. 다음 내용 추가:
```

```nginx
upstream dongta_app {
    server localhost:8000;
}

server {
    listen 80;
    server_name dongta.theuit.info www.dongta.theuit.info;

    # HTTP → HTTPS 리디렉트
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dongta.theuit.info www.dongta.theuit.info;

    # SSL 인증서 (Let's Encrypt 권장)
    ssl_certificate /etc/letsencrypt/live/dongta.theuit.info/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dongta.theuit.info/privkey.pem;

    # SSL 보안 설정
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # 정적 파일 및 미디어
    location /static/ {
        alias /app/dongta-django/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /app/dongta-django/media/;
        expires 7d;
    }

    # API 프록시
    location / {
        proxy_pass http://dongta_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }

    # Health check 엔드포인트
    location /health/ {
        proxy_pass http://dongta_app;
    }
}
```

```bash
# 4. Nginx 활성화
sudo ln -s /etc/nginx/sites-available/dongta /etc/nginx/sites-enabled/dongta
sudo nginx -t
sudo systemctl restart nginx

# 5. SSL 인증서 (Let's Encrypt)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot certonly --nginx -d dongta.theuit.info -d www.dongta.theuit.info
```

---

### Step 3: 환경 설정 파일 업로드

```bash
# 로컬에서 .env.prod 파일을 서버로 업로드
scp -i your-key.pem dongta-django/.env.prod ubuntu@your-server-ip:/app/dongta-django/.env.prod

# 또는 SSH로 직접 수정
ssh -i your-key.pem ubuntu@your-server-ip << 'EOF'
cd /app/dongta-django
nano .env.prod
# 실제 값들을 입력합니다
EOF
```

---

### Step 4: Docker 및 배포 자동화

#### 초기 배포 (수동)

```bash
ssh -i your-key.pem ubuntu@your-server-ip << 'EOF'
cd /app/dongta-django

# 최신 코드 받기
git pull origin main

# 환경 설정 확인
ls -la .env.prod

# Docker Compose 시작
docker-compose -f docker-compose.prod.yml up -d

# 데이터베이스 마이그레이션
docker-compose -f docker-compose.prod.yml exec -T web python manage.py migrate

# 정적 파일 수집
docker-compose -f docker-compose.prod.yml exec -T web python manage.py collectstatic --noinput

# 상태 확인
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs web
EOF
```

#### 배포 후 확인

```bash
# Health check
curl https://dongta.theuit.info/health/

# API 응답 확인
curl -H "Content-Type: application/json" https://dongta.theuit.info/api/v1/accounts/me/

# 로그 확인
ssh -i your-key.pem ubuntu@your-server-ip tail -f /var/log/django/dongta.log
```

---

### Step 5: 모니터링 및 유지보수

#### 일일 점검 항목

- [ ] Sentry 오류 모니터링
- [ ] 로그 파일 확인
- [ ] 디스크 용량 확인
- [ ] 데이터베이스 백업 확인
- [ ] 성능 메트릭 확인

#### 자동 백업 설정

```bash
# PostgreSQL 자동 백업 (매일 자정)
0 0 * * * pg_dump -h localhost -U dongta_user dongtadb_prod | gzip > /backups/dongta_$(date +\%Y\%m\%d).sql.gz
```

#### 로그 로테이션

```bash
# /etc/logrotate.d/dongta 파일 생성
/var/log/django/dongta.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 ubuntu ubuntu
    sharedscripts
    postrotate
        docker-compose -f /app/dongta-django/docker-compose.prod.yml kill -s HUP web
    endscript
}
```

---

## 🔄 CI/CD 자동 배포 흐름

GitHub Actions Workflow 자동 실행:

```
1. 코드 푸시 (git push origin main)
   ↓
2. Lint & Test (flake8, pytest)
   ↓
3. Docker 이미지 빌드 및 푸시 (Docker Hub)
   ↓
4. 운영 서버 배포 (SSH + docker-compose)
   ↓
5. 배포 완료 알림 (Slack)
```

배포 상태 확인:
- GitHub: Actions 탭에서 워크플로우 상태 확인
- Slack: 배포 완료/실패 알림 수신

---

## 🆘 문제 해결

### Docker 이미지 빌드 실패

```bash
# 로컬에서 빌드 테스트
cd dongta-django
docker build -t dongta:latest .

# 빌드 로그 확인
docker build --progress=plain -t dongta:latest . 2>&1 | tail -50
```

### 데이터베이스 연결 오류

```bash
# PostgreSQL 연결 테스트
psql "postgresql://dongta_user:password@host:5432/dongtadb_prod"

# 마이그레이션 상태 확인
docker-compose -f docker-compose.prod.yml exec web python manage.py showmigrations

# 마이그레이션 재실행
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate --plan
```

### Celery 작업 큐 확인

```bash
# Celery 워커 상태
docker-compose -f docker-compose.prod.yml exec celery-sync celery -A config inspect active

# 대기 중인 작업
docker-compose -f docker-compose.prod.yml exec celery-sync celery -A config inspect reserved
```

---

## 📞 지원

- **Sentry**: 오류 모니터링 대시보드
- **CloudWatch**: AWS 로그 및 메트릭
- **Slack**: 배포 및 알림 통합

---

**마이그레이션 배포가 성공적으로 완료되길 기원합니다!** 🎉
