# ✅ 배포 전 최종 체크리스트

## 📋 배포 단계별 체크리스트

### Phase 1: 코드 준비 ✅

- [x] 모든 코드 변경사항 커밋
- [x] GitHub Actions workflow 파일 생성 (.github/workflows/deploy.yml)
- [x] .env.prod 파일 생성 (환경변수 템플릿)
- [x] DEPLOYMENT_GUIDE.md 문서화
- [x] Dockerfile 검증
- [x] requirements.txt 검증

### Phase 2: GitHub 설정 (진행 중)

**실행 항목:**
- [ ] GitHub에 코드 푸시 (`git push origin main`)
- [ ] GitHub Settings → Secrets and variables → Actions 접속
- [ ] 다음 환경변수 추가:

```
DOCKER_USERNAME=<your-docker-username>
DOCKER_PASSWORD=<your-docker-password>
DEPLOY_HOST=<your-server-ip-or-domain>
DEPLOY_USER=<ssh-username>
DEPLOY_KEY=<ssh-private-key-content>
SECRET_KEY=<generate-new-django-secret>
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://host:6379/0
MYSQL_DATABASE_URL=mysql://user:pass@host:3306/db
ALLOWED_HOSTS=dongta.theuit.info,www.dongta.theuit.info
SENTRY_DSN=<your-sentry-dsn>
DANAL_CPID=<danal-merchant-id>
DANAL_KEY=<danal-api-key>
AWS_ACCESS_KEY_ID=<aws-access-key>
AWS_SECRET_ACCESS_KEY=<aws-secret-key>
AWS_STORAGE_BUCKET_NAME=dongta-prod-uploads
AWS_S3_REGION_NAME=ap-northeast-2
SLACK_WEBHOOK=<slack-webhook-url> (선택사항)
```

### Phase 3: 운영 서버 준비

**선행 작업:**
- [ ] AWS EC2 인스턴스 생성 (t3.medium 이상 권장)
- [ ] 보안 그룹 설정 (80, 443, 22 포트 허용)
- [ ] Elastic IP 할당 및 도메인 연결
- [ ] PostgreSQL RDS 인스턴스 생성 (production)
- [ ] ElastiCache Redis 인스턴스 생성
- [ ] S3 버킷 생성 (dongta-prod-uploads)

**서버 설정:**
```bash
# SSH로 서버 접속
ssh -i your-key.pem ubuntu@your-server-ip

# 패키지 설치
sudo apt update && sudo apt install -y \
    docker.io docker-compose git curl \
    postgresql-client nginx certbot python3-certbot-nginx

# Docker 권한 설정
sudo usermod -aG docker ubuntu

# 애플리케이션 디렉토리
mkdir -p /app/dongta-django /var/log/django
sudo chown ubuntu:ubuntu /var/log/django

# .env.prod 파일 업로드
# (로컬에서) scp -i your-key.pem .env.prod ubuntu@your-server-ip:/app/dongta-django/
```

- [ ] Nginx 설정 (DEPLOYMENT_GUIDE.md 참고)
- [ ] SSL 인증서 설정 (Let's Encrypt)
- [ ] 로그 디렉토리 권한 설정

### Phase 4: 초기 배포

**배포 작업:**
```bash
cd /app/dongta-django
git clone https://github.com/brigon1218/dongta_ver2.git .
docker-compose -f docker-compose.prod.yml up -d
docker-compose -f docker-compose.prod.yml exec -T web python manage.py migrate
docker-compose -f docker-compose.prod.yml exec -T web python manage.py collectstatic --noinput
```

**검증:**
- [ ] Health check 성공: `curl https://dongta.theuit.info/health/`
- [ ] API 응답 확인: `curl https://dongta.theuit.info/api/v1/`
- [ ] Sentry 오류 모니터링 작동 확인
- [ ] 로그 파일 생성 확인: `tail -f /var/log/django/dongta.log`

### Phase 5: CI/CD 자동화 검증

**자동 배포 테스트:**
- [ ] GitHub Actions workflow 활성화 확인
- [ ] 테스트 커밋 푸시 및 workflow 실행 확인
- [ ] 배포 성공 확인 (Slack 알림 수신)
- [ ] 운영 서버에서 새 버전 배포 확인

### Phase 6: 모니터링 설정

**모니터링 도구 연결:**
- [ ] Sentry 프로젝트 생성 및 DSN 설정
- [ ] CloudWatch 로그 확인
- [ ] Slack 채널 알림 활성화
- [ ] 일일 백업 스케줄 설정

### Phase 7: 최종 검증

**테스트 환경 점검:**
- [ ] 웹사이트 접속 가능 (dongta.theuit.info)
- [ ] HTTPS 보안 연결 (초록 자물쇠)
- [ ] 모든 API 엔드포인트 응답 확인
  - [ ] 인증 (회원가입, 로그인)
  - [ ] 결제 (다날 테스트)
  - [ ] 채용정보 조회
  - [ ] 동타114 조회
  - [ ] 게시판 조회
  - [ ] 마이페이지
- [ ] 데이터베이스 마이그레이션 완료
- [ ] 정적 파일(CSS, JS, 이미지) 로드 확인
- [ ] 성능 메트릭 정상 범위

---

## 🚨 Critical Checks Before Go-Live

| 항목 | 확인 | 담당자 | 완료 |
|------|------|--------|------|
| 데이터 백업 | 운영 데이터 백업 완료 | DevOps | [ ] |
| SSL 인증서 | HTTPS 설정 확인 | DevOps | [ ] |
| 보안 설정 | 방화벽, 보안 그룹 설정 | SecOps | [ ] |
| 모니터링 | Sentry, CloudWatch 활성화 | DevOps | [ ] |
| 성능 | 응답 시간 < 500ms | QA | [ ] |
| 부하 테스트 | 동시 사용자 1000+ 테스트 | QA | [ ] |
| DNS 설정 | A/CNAME 레코드 확인 | DevOps | [ ] |
| 이메일 | SMTP 설정 확인 | Backend | [ ] |
| 결제 | 다날 테스트 트랜잭션 | Backend | [ ] |

---

## 📞 비상 연락처

| 역할 | 이름 | 연락처 |
|------|------|--------|
| DevOps | - | - |
| Backend | - | - |
| Frontend | - | - |
| Database | - | - |

---

## 📅 배포 일정

| 단계 | 예상 일정 | 상태 |
|------|---------|------|
| Phase 1: 코드 준비 | ✅ 완료 | |
| Phase 2: GitHub 설정 | 2026-03-09 | 진행 중 |
| Phase 3: 서버 준비 | 2026-03-10 | 예정 |
| Phase 4: 초기 배포 | 2026-03-10 | 예정 |
| Phase 5: 자동화 검증 | 2026-03-11 | 예정 |
| Phase 6: 모니터링 | 2026-03-11 | 예정 |
| Phase 7: Go-Live | 2026-03-12 | 예정 |

---

## 🔄 롤백 계획

배포 실패 시:

```bash
# 이전 버전으로 롤백
cd /app/dongta-django
git revert HEAD
docker-compose -f docker-compose.prod.yml restart web
docker-compose -f docker-compose.prod.yml logs -f web
```

---

## 📝 배포 후 리포트

배포 완료 후 다음 정보를 문서화:

- 배포 시간
- 배포된 커밋 해시
- 주요 변경사항
- 성능 메트릭 (응답 시간, 오류율 등)
- 문제 및 해결사항

---

**모든 항목을 확인한 후 배포를 진행하세요!** 🚀
