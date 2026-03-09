# Phase 2: 하이브리드 연동 구현 가이드

> **목표**: Nginx 리버스 프록시, Celery 데이터 동기화, Danal 결제 통합 구현
>
> **예상 기간**: 6개월 (Phase 2-1 ~ 2-3)
> **AWS 서버**: 52.79.148.197 (ubuntu@dongta.theuit.info)
> **문서 참고**: docs/02-design/features/하이브리드_연동.design.md

---

## 📋 구현 순서 (Implementation Checklist)

### Phase 2-1: Nginx 리버스 프록시 구축 (Month 1-2)

#### Step 1: 로컬 개발 환경 준비
- [ ] Nginx 설정 파일 작성 (로컬 테스트)
- [ ] Gunicorn + Systemd 설정
- [ ] Docker Compose 업데이트 (Nginx 추가)
- [ ] 로컬 환경 테스트

**Key Files:**
```
config/nginx/
├── nginx.conf
├── conf.d/
│   ├── upstream.conf
│   ├── ssl.conf
│   └── api.conf
└── sites-enabled/
    └── www.dongta.com.conf

systemd/
├── dongta-django.service
└── dongta-django.socket
```

**Commands:**
```bash
# Nginx 설정 검증
docker exec nginx nginx -t

# Gunicorn 포트 확인
lsof -i :8000,8001,8002

# Docker Compose 재시작
docker-compose restart nginx gunicorn
```

#### Step 2: AWS 스테이징 환경 배포
- [ ] EC2 인스턴스 연결 (SSH)
- [ ] 필수 패키지 설치
- [ ] Nginx 설정 적용
- [ ] SSL 인증서 발급 (Let's Encrypt)
- [ ] Gunicorn 서비스 시작

**AWS Server Info:**
```
IP: 52.79.148.197
User: ubuntu
Key: /Users/yonghwanahn/workspace/vibe_coding/keystore/dongta-django.pem
Root: /home/ubuntu/work_01
Domain: dongta.theuit.info
```

**Deployment Steps:**
```bash
# 1. 서버 연결
ssh -i /Users/yonghwanahn/workspace/vibe_coding/keystore/dongta-django.pem \
    ubuntu@52.79.148.197

# 2. 의존성 설치
sudo apt-get update
sudo apt-get install -y nginx python3-pip python3-venv gunicorn

# 3. 프로젝트 클론
cd /home/ubuntu
git clone <repo> work_01
cd work_01

# 4. Python 가상환경 설정
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/production.txt

# 5. Nginx 설정 복사
sudo cp config/nginx/www.dongta.com.conf /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-enabled/www.dongta.com.conf /etc/nginx/conf.d/

# 6. Systemd 서비스 설정
sudo cp systemd/dongta-django.service /etc/systemd/system/
sudo cp systemd/dongta-django.socket /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start dongta-django

# 7. Nginx 시작
sudo systemctl start nginx
sudo systemctl enable nginx

# 8. 헬스 체크
curl http://dongta.theuit.info/health
```

#### Step 3: SSL/TLS 설정
- [ ] Let's Encrypt 인증서 발급
- [ ] Nginx SSL 설정 적용
- [ ] 인증서 자동 갱신 설정

```bash
# Certbot 설치
sudo apt-get install -y certbot python3-certbot-nginx

# 인증서 발급
sudo certbot certonly --nginx -d dongta.theuit.info

# Nginx에 SSL 설정 추가
sudo certbot renew --dry-run  # 테스트
```

---

### Phase 2-2: 데이터 동기화 파이프라인 (Month 3-4)

#### Step 4: Celery + Redis 환경 구축
- [ ] Redis 설치 및 설정
- [ ] Celery 의존성 설치
- [ ] Celery 설정 파일 작성
- [ ] Celery Beat 설정

**Key Files:**
```
config/celery.py
    ├── CELERY_BROKER_URL
    ├── CELERY_RESULT_BACKEND
    ├── CELERY_QUEUES (sync, payment, default)
    └── CELERY_BEAT_SCHEDULE

docker-compose.yml
    ├── redis service
    ├── celery-sync worker
    ├── celery-payment worker
    └── celery-beat service
```

**Installation:**
```bash
# Redis 설치
sudo apt-get install -y redis-server

# Python 패키지
pip install celery redis

# Celery 워커 시작
celery -A config worker -l info -Q sync,payment,default

# Celery Beat 시작
celery -A config beat -l info
```

#### Step 5: MySQL 트리거 작성
- [ ] TBL_EVENT_OUTBOX 테이블 생성
- [ ] MySQL 트리거 작성 (회원, 결제)
- [ ] 트리거 테스트

**SQL Script:**
```sql
-- File: scripts/01_create_event_outbox.sql

CREATE TABLE IF NOT EXISTS TBL_EVENT_OUTBOX (
    event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id INT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    payload JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP NULL,
    retry_count INT DEFAULT 0,
    error_message TEXT NULL,

    KEY idx_processed (processed, created_at),
    KEY idx_aggregate (aggregate_type, aggregate_id)
);

-- 회원 정보 업데이트 트리거
CREATE TRIGGER tg_member_update AFTER UPDATE ON TBL_MEMB
FOR EACH ROW
BEGIN
    INSERT INTO TBL_EVENT_OUTBOX
    (aggregate_type, aggregate_id, event_type, payload)
    VALUES (
        'member',
        NEW.NO_MEMB,
        'updated',
        JSON_OBJECT(
            'no_memb', NEW.NO_MEMB,
            'id_member', NEW.ID_MEMBER,
            'nm_member', NEW.NM_MEMBER,
            'email', NEW.EMAIL,
            'phone', NEW.TEL
        )
    );
END;

-- 적용
mysql -h <RDS_HOST> -u <USER> -p <DB> < scripts/01_create_event_outbox.sql
```

#### Step 6: Django Celery Task 구현
- [ ] 회원 정보 동기화 Task
- [ ] 데이터 검증 Task
- [ ] 정기 정크리닝 Task

**Python Code:**
```python
# File: apps/sync/tasks.py

from celery import shared_task
from django.db import transaction
import json
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, queue='sync')
def sync_member_data(self, event_id: int):
    """MySQL → PostgreSQL 회원 정보 동기화"""
    from apps.sync.models import EventOutbox
    from apps.accounts.models import Member

    try:
        event = EventOutbox.objects.get(event_id=event_id)
        payload = json.loads(event.payload)

        with transaction.atomic():
            member, created = Member.objects.update_or_create(
                no_memb=payload['no_memb'],
                defaults={
                    'id_member': payload['id_member'],
                    'nm_member': payload['nm_member'],
                    'email': payload['email'],
                    'phone': payload['phone'],
                }
            )

            event.processed = True
            event.processed_at = timezone.now()
            event.save()

        logger.info(f"[SYNC] Successfully synced member {payload['no_memb']}")
        return {'status': 'success', 'member_id': member.id}

    except Exception as e:
        logger.error(f"[SYNC] Failed to sync event {event_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        return {'status': 'failed', 'reason': str(e)}
```

#### Step 7: 동기화 검증 도구 개발
- [ ] 데이터 일관성 검증 스크립트
- [ ] 모니터링 대시보드 (선택)
- [ ] 알림 설정

```python
# File: apps/sync/management/commands/verify_sync.py

from django.core.management.base import BaseCommand
from django.db import connection
from apps.accounts.models import Member

class Command(BaseCommand):
    def handle(self, *args, **options):
        # MySQL 회원 수
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM TBL_MEMB WHERE DL_GB = 'N'")
            mysql_count = cursor.fetchone()[0]

        # PostgreSQL 회원 수
        postgres_count = Member.objects.filter(is_deleted=False).count()

        # 검증
        discrepancy = abs(mysql_count - postgres_count)

        self.stdout.write(
            f"MySQL: {mysql_count}, PostgreSQL: {postgres_count}, Diff: {discrepancy}"
        )

        if discrepancy > 10:
            self.stdout.write(self.style.WARNING(f"⚠️ 데이터 불일치 감지!"))
```

---

### Phase 2-3: 결제 시스템 통합 (Month 5-6)

#### Step 8: Danal 결제 API 래핑
- [ ] Danal API 클라이언트 작성
- [ ] 결제 요청/응답 처리
- [ ] 에러 핸들링

**Key Files:**
```
apps/payment/
├── models.py (Payment model)
├── views.py (PaymentView, DanalCallbackView)
├── serializers.py (PaymentSerializer)
├── services.py (DanalPaymentService)
└── urls.py
```

#### Step 9: 결제 결과 양쪽 DB 기록
- [ ] Django: PostgreSQL 저장
- [ ] PHP: MySQL 저장 (Celery Task)
- [ ] 이중 기록 검증

#### Step 10: 테스트 및 배포
- [ ] 통합 테스트 (무중단 배포)
- [ ] 부하 테스트 (1000 RPS)
- [ ] 30일 모니터링

---

## 🔧 필수 파일 생성 목록

### Nginx 설정

**File: `config/nginx/nginx.conf`**
```nginx
user www-data;
worker_processes auto;
worker_rlimit_nofile 65535;

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 4096;
    use epoll;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    access_log /var/log/nginx/access.log combined;

    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
```

**File: `config/nginx/conf.d/upstream.conf`**
```nginx
upstream django_backend {
    least_conn;
    server 127.0.0.1:8000 weight=1 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8001 weight=1 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8002 weight=1 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

upstream php_backend {
    server 127.0.0.1:80 max_fails=3 fail_timeout=30s;
    keepalive 32;
}
```

**File: `config/nginx/sites-enabled/www.dongta.com.conf`**
```nginx
server {
    listen 80;
    server_name dongta.theuit.info;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dongta.theuit.info;

    ssl_certificate /etc/letsencrypt/live/dongta.theuit.info/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dongta.theuit.info/privkey.pem;

    location /api/v1/ {
        proxy_pass http://django_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location / {
        proxy_pass http://php_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /health {
        access_log off;
        return 200 '{"status":"ok"}';
        add_header Content-Type application/json;
    }
}
```

### Systemd 서비스

**File: `systemd/dongta-django.service`**
```ini
[Unit]
Description=Dongta Django Gunicorn Server
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/dongta-django

Environment="PATH=/var/www/dongta-django/venv/bin"
ExecStart=/var/www/dongta-django/venv/bin/gunicorn \
    --workers 3 \
    --worker-class sync \
    --timeout 30 \
    --bind unix:/var/run/dongta-django.sock \
    config.wsgi:application

Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

**File: `systemd/dongta-django.socket`**
```ini
[Unit]
Description=Dongta Django Gunicorn Socket

[Socket]
ListenStream=/var/run/dongta-django.sock

[Install]
WantedBy=sockets.target
```

### Docker Compose 업데이트

**File: `docker-compose.yml` (Nginx 추가)**
```yaml
version: '3.8'

services:
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./config/nginx/conf.d:/etc/nginx/conf.d
      - ./config/nginx/sites-enabled:/etc/nginx/sites-enabled
    depends_on:
      - web
    restart: unless-stopped

  web:
    build: .
    command: gunicorn --workers 3 --bind 0.0.0.0:8000 config.wsgi:application
    volumes:
      - .:/app
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: dongta
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  celery:
    build: .
    command: celery -A config worker -l info -Q sync,payment,default
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  celery-beat:
    build: .
    command: celery -A config beat -l info
    depends_on:
      - redis
    restart: unless-stopped

volumes:
  postgres_data:
```

---

## 🚀 배포 스크립트

**File: `scripts/deploy.sh`**

```bash
#!/bin/bash

# AWS EC2 배포 스크립트
# Usage: ./scripts/deploy.sh

set -e

SERVER_IP="52.79.148.197"
SERVER_USER="ubuntu"
SSH_KEY="/Users/yonghwanahn/workspace/vibe_coding/keystore/dongta-django.pem"
REMOTE_DIR="/home/ubuntu/work_01"

echo "[1/5] 서버 연결 테스트..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "echo OK"

echo "[2/5] 최신 코드 풀..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "cd $REMOTE_DIR && git pull origin main"

echo "[3/5] 패키지 설치..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "cd $REMOTE_DIR && source venv/bin/activate && pip install -r requirements/production.txt"

echo "[4/5] 마이그레이션..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "cd $REMOTE_DIR && source venv/bin/activate && python manage.py migrate"

echo "[5/5] 서비스 재시작..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "sudo systemctl restart dongta-django nginx"

echo "✅ 배포 완료!"
```

---

## 📊 진행 상황 추적

| Phase | Step | 작업 | Status |
|-------|------|------|--------|
| 2-1 | 1 | Nginx 설정 작성 | ⏳ Pending |
| 2-1 | 2 | AWS 배포 | ⏳ Pending |
| 2-1 | 3 | SSL 설정 | ⏳ Pending |
| 2-2 | 4 | Celery + Redis | ⏳ Pending |
| 2-2 | 5 | MySQL 트리거 | ⏳ Pending |
| 2-2 | 6 | Django Task 구현 | ⏳ Pending |
| 2-2 | 7 | 검증 도구 | ⏳ Pending |
| 2-3 | 8 | Danal API 래핑 | ⏳ Pending |
| 2-3 | 9 | 결제 양쪽 기록 | ⏳ Pending |
| 2-3 | 10 | 통합 테스트 | ⏳ Pending |

---

## ✅ 다음 단계

1. **Step 1**: Nginx 설정 파일 생성
2. **Step 2**: AWS 서버에 배포
3. **Step 3**: SSL 인증서 설정
4. **Step 4-7**: 데이터 동기화 구현
5. **Step 8-10**: 결제 시스템 통합

각 Step별 세부 명령어와 코드는 위의 "필수 파일 생성 목록"과 "배포 스크립트"를 참고하세요.

---

## 📞 문제 해결

### Nginx 에러
```bash
# 설정 검증
sudo nginx -t

# 로그 확인
sudo tail -f /var/log/nginx/error.log
```

### Celery 문제
```bash
# 워커 상태 확인
celery -A config inspect active

# 실패한 작업 확인
celery -A config inspect reserved
```

### 데이터 동기화 검증
```bash
python manage.py verify_sync
```

---

**작성일**: 2026-03-06
**버전**: 1.0.0
