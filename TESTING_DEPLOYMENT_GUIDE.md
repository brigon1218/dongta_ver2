# 🧪 테스트 배포 가이드

**테스트 도메인**: `dongta.theuit.info`

> ⚠️ 이 가이드는 운영 배포 전에 테스트 환경에서 배포를 검증하기 위한 것입니다.

---

## 📋 빠른 시작

### 1단계: 환경 설정 확인

```bash
cd dongta-django

# 테스트 환경 파일 확인
ls -la .env.staging docker-compose.staging.yml

# 필요시 .env.staging 수정
nano .env.staging
```

### 2단계: Docker 빌드 및 시작

```bash
# 테스트 환경 시작 (로컬 또는 테스트 서버)
docker-compose -f docker-compose.staging.yml build
docker-compose -f docker-compose.staging.yml up -d

# 상태 확인
docker-compose -f docker-compose.staging.yml ps
```

### 3단계: 데이터베이스 설정

```bash
# 마이그레이션 실행
docker-compose -f docker-compose.staging.yml exec web python manage.py migrate

# 정적 파일 수집
docker-compose -f docker-compose.staging.yml exec web python manage.py collectstatic --noinput

# 슈퍼유저 생성 (선택사항)
docker-compose -f docker-compose.staging.yml exec web python manage.py createsuperuser
```

### 4단계: 접속 및 테스트

```bash
# 로컬 테스트
curl http://localhost:8001/health/

# 원격 테스트 (도메인 설정된 경우)
curl https://dongta.theuit.info/health/
```

---

## 🔧 포트 매핑

| 서비스 | 테스트 포트 | 용도 |
|--------|-----------|------|
| Gunicorn | 8001 | Django API |
| Nginx HTTP | 8080 | 웹 프록시 |
| Nginx HTTPS | 8443 | SSL 프록시 |
| PostgreSQL | 5433 | 데이터베이스 |
| Redis | 6380 | 캐시 |

### 로컬에서 API 테스트

```bash
# 기본 요청
curl http://localhost:8001/api/v1/

# JSON 형식 요청
curl -H "Content-Type: application/json" \
  http://localhost:8001/api/v1/accounts/me/

# POST 요청 (회원가입)
curl -X POST http://localhost:8001/api/v1/accounts/signup/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123!",
    "password_confirm": "TestPassword123!",
    "name": "테스트 사용자"
  }'
```

---

## 📊 테스트 체크리스트

### Health Check

- [ ] `curl https://dongta.theuit.info/health/` 응답 확인
- [ ] 상태 코드 200 OK
- [ ] 응답 시간 < 500ms

### API 엔드포인트 테스트

#### 인증 (Accounts)

- [ ] **회원가입**: POST `/api/v1/accounts/signup/`
- [ ] **로그인**: POST `/api/v1/accounts/login/`
- [ ] **토큰 리프레시**: POST `/api/v1/accounts/token/refresh/`
- [ ] **프로필 조회**: GET `/api/v1/accounts/me/`
- [ ] **프로필 수정**: PATCH `/api/v1/accounts/me/`
- [ ] **비밀번호 변경**: POST `/api/v1/accounts/change-password/`
- [ ] **회원 탈퇴**: POST `/api/v1/accounts/withdraw/`

#### 동타114 (Business)

- [ ] **목록 조회**: GET `/api/v1/business114/`
- [ ] **검색**: GET `/api/v1/business114/?search=keyword`
- [ ] **필터**: GET `/api/v1/business114/?industry_type=1`
- [ ] **상세 조회**: GET `/api/v1/business114/{id}/`
- [ ] **생성**: POST `/api/v1/business114/` (로그인 필요)
- [ ] **수정**: PATCH `/api/v1/business114/{id}/` (본인 확인)
- [ ] **삭제**: DELETE `/api/v1/business114/{id}/` (본인 확인)

#### 채용정보 (Recruit)

- [ ] **공고 목록**: GET `/api/v1/recruit/job-notices/`
- [ ] **공고 상세**: GET `/api/v1/recruit/job-notices/{id}/`
- [ ] **공고 생성**: POST `/api/v1/recruit/job-notices/` (로그인 필요)
- [ ] **공고 수정**: PATCH `/api/v1/recruit/job-notices/{id}/`
- [ ] **공고 삭제**: DELETE `/api/v1/recruit/job-notices/{id}/`

#### 게시판 (Board)

- [ ] **게시글 목록**: GET `/api/v1/board/posts/`
- [ ] **게시글 상세**: GET `/api/v1/board/posts/{id}/`
- [ ] **게시글 생성**: POST `/api/v1/board/posts/`
- [ ] **댓글 생성**: POST `/api/v1/board/posts/{id}/comments/`
- [ ] **추천**: POST `/api/v1/board/posts/{id}/like/`

#### 결제 (Payment)

- [ ] **잔액 조회**: GET `/api/v1/payment/balance/`
- [ ] **결제 내역**: GET `/api/v1/payment/history/`
- [ ] **다날 준비**: POST `/api/v1/payment/danal/ready/`
- [ ] **다날 승인**: POST `/api/v1/payment/danal/approve/`
- [ ] **다날 취소**: POST `/api/v1/payment/danal/cancel/`

#### 마이페이지 (MyPage)

- [ ] **프로필 조회**: GET `/api/v1/mypage/profile/`
- [ ] **활동 요약**: GET `/api/v1/mypage/activity-summary/`
- [ ] **포인트 내역**: GET `/api/v1/mypage/point-history/`

---

## 🐛 디버깅

### 로그 확인

```bash
# 웹 서버 로그
docker-compose -f docker-compose.staging.yml logs -f web

# Celery 로그
docker-compose -f docker-compose.staging.yml logs -f celery-sync

# 모든 로그
docker-compose -f docker-compose.staging.yml logs -f
```

### 데이터베이스 접속

```bash
# PostgreSQL 접속
psql -h localhost -p 5433 -U dongta_user -d dongtadb_test

# MySQL (하이브리드 기간)
mysql -h localhost -u admin_user -p
```

### 캐시 확인

```bash
# Redis 접속
redis-cli -p 6380

# 명령어
PING               # 연결 확인
KEYS *             # 모든 키 확인
GET <key>          # 값 확인
DEL <key>          # 키 삭제
FLUSHALL           # 모든 데이터 삭제
```

---

## 🚨 문제 해결

### 포트 충돌

```bash
# 포트 사용 프로세스 확인
lsof -i :8001

# 강제 종료
kill -9 <PID>
```

### 데이터베이스 연결 실패

```bash
# 데이터베이스 상태 확인
docker-compose -f docker-compose.staging.yml ps db

# 데이터베이스 재시작
docker-compose -f docker-compose.staging.yml restart db
```

### 마이그레이션 오류

```bash
# 마이그레이션 상태 확인
docker-compose -f docker-compose.staging.yml exec web python manage.py showmigrations

# 롤백
docker-compose -f docker-compose.staging.yml exec web python manage.py migrate <app> <migration_number>

# 스키마 리셋 (테스트 전용!)
docker-compose -f docker-compose.staging.yml exec web python manage.py flush --no-input
```

---

## 📊 성능 테스트

### 부하 테스트 (Apache Bench)

```bash
# 100 요청, 10 동시 연결
ab -n 100 -c 10 https://dongta.theuit.info/api/v1/

# 결과 분석
# Requests per second: 처리량
# Time per request: 평균 응답 시간
# Failed requests: 실패한 요청
```

### 응답 시간 측정

```bash
# 단일 요청 시간
time curl https://dongta.theuit.info/api/v1/

# JSON 응답 시간
curl -w "Total: %{time_total}s\n" -o /dev/null -s https://dongta.theuit.info/api/v1/
```

---

## 🔄 테스트에서 운영으로 마이그레이션

테스트 완료 후 운영으로 전환:

1. **환경 파일 수정**
   ```bash
   # .env.prod 값을 실제 운영 값으로 변경
   nano dongta-django/.env.prod
   ```

2. **도메인 설정**
   ```bash
   # DNS A 레코드를 운영 서버로 변경
   # 또는 Nginx 도메인 설정 수정
   ```

3. **SSL 인증서 설정**
   ```bash
   # Let's Encrypt 인증서 발급
   sudo certbot certonly --nginx -d dongta.com -d www.dongta.com
   ```

4. **운영 배포**
   ```bash
   # 운영 docker-compose 사용
   docker-compose -f docker-compose.prod.yml up -d
   ```

---

## 📞 지원

문제 발생 시:

1. 로그 확인: `docker-compose -f docker-compose.staging.yml logs -f`
2. Health check: `curl https://dongta.theuit.info/health/`
3. API 테스트: 위의 테스트 체크리스트 확인

---

**테스트 배포가 성공하면 운영 환경으로 진행할 준비가 된 것입니다!** ✅
