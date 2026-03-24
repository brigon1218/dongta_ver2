# 🎮 서버 제어 스크립트 사용 가이드

**스크립트**: `server_control.sh`
**버전**: 1.0
**작성일**: 2026-03-12

---

## 📋 개요

원격 AWS 서버의 Docker 서비스를 로컬에서 쉽게 관리할 수 있는 스크립트입니다.

```
SSH 접속 → Docker 명령 실행 → 결과 표시
```

---

## 🚀 빠른 시작

### 1단계: 스크립트 위치 이동
```bash
cd /Volumes/sk-p31/workspace/vibe_coding/work_01
```

### 2단계: 명령어 실행
```bash
# 서버 상태 확인
./server_control.sh status

# 서버 시작
./server_control.sh start

# 서버 중지
./server_control.sh stop
```

---

## 📚 명령어 상세

### 1️⃣ **start** - 서버 시작

모든 Docker 서비스를 시작합니다.

```bash
./server_control.sh start
```

**동작**:
- Django 웹 서버 시작
- PostgreSQL 데이터베이스 시작
- Redis 캐시 시작
- Celery 워커 시작 (3개)
- Nginx 준비

**소요시간**: ~5초

**출력 예**:
```
🚀 서버 시작 중...
═══════════════════════════════════════════════════════
✅ 서버 시작 완료!

📊 Docker 컨테이너 상태
═══════════════════════════════════════════════════════
NAME                             STATUS
dongta-django-web-1              Up 2 seconds
dongta-django-db-1               Up 2 seconds (healthy)
dongta-django-redis-1            Up 2 seconds (healthy)
dongta-django-celery-sync-1      Up 1 second
dongta-django-celery-sync-2      Up 1 second
dongta-django-celery-payment-1   Up 1 second
dongta-django-celery-beat-1      Up 1 second
```

---

### 2️⃣ **stop** - 서버 중지

모든 Docker 서비스를 중지합니다.

```bash
./server_control.sh stop
```

**동작**:
- 모든 컨테이너 중지
- 데이터 보존 (DB 데이터 유지)
- 네트워크 정리

**소요시간**: ~3초

**주의**: 웹사이트에 접속할 수 없게 됩니다.

---

### 3️⃣ **restart** - 서버 재시작

서버를 중지했다가 다시 시작합니다.

```bash
./server_control.sh restart
```

**동작**:
1. 서버 중지
2. 2초 대기
3. 서버 시작

**소요시간**: ~10초

**용도**:
- 설정 변경 적용
- 문제 해결
- 정기 유지보수

---

### 4️⃣ **status** - 서버 상태 확인

현재 실행 중인 컨테이너 상태를 확인합니다.

```bash
./server_control.sh status
```

**출력**:
```
📊 Docker 컨테이너 상태
═══════════════════════════════════════════════════════
NAME                             STATUS              PORTS
dongta-django-web-1              Up 1 hour           0.0.0.0:8000->8000/tcp
dongta-django-db-1               Up 1 hour (healthy) 0.0.0.0:5432->5432/tcp
dongta-django-redis-1            Up 1 hour (healthy) 0.0.0.0:6379->6379/tcp
dongta-django-celery-sync-1      Up 1 hour
dongta-django-celery-sync-2      Up 1 hour
dongta-django-celery-payment-1   Up 1 hour
dongta-django-celery-beat-1      Up 1 hour
```

**해석**:
- `Up X`: 정상 실행 중
- `(healthy)`: 헬스체크 통과
- Port 번호: 서비스 포트

---

### 5️⃣ **logs** - 서비스 로그 확인

서비스의 실시간 로그를 확인합니다.

```bash
# Django 웹 서버 로그 (기본)
./server_control.sh logs

# 특정 서비스 로그
./server_control.sh logs web      # Django
./server_control.sh logs db       # PostgreSQL
./server_control.sh logs redis    # Redis
./server_control.sh logs celery-sync  # Celery 워커

# 로그에서 나가기: Ctrl+C
```

**용도**:
- 에러 메시지 확인
- 요청 추적
- 성능 분석

**예제 출력**:
```
[2026-03-12 15:30:00] INFO - Server started
[2026-03-12 15:30:05] INFO - Database connected
[2026-03-12 15:30:10] GET /api/v1/business/ 200 45ms
[2026-03-12 15:30:12] GET /api/v1/recruit/notices/ 200 52ms
```

---

### 6️⃣ **health-check** - 헬스체크

웹사이트와 API가 정상 작동하는지 확인합니다.

```bash
./server_control.sh health-check
```

**확인 항목**:
- 🌐 메인 페이지 응답
- 🏢 Business API 응답
- 📚 API Docs 응답
- 📊 Docker 서비스 개수

**출력 예**:
```
🏥 헬스체크 실행 중...
═══════════════════════════════════════════════════════
🌐 메인 페이지: ✅ HTTP 301 (리다이렉트)
🏢 Business API: ✅ HTTP 200
📚 API Docs: ✅ HTTP 200

📊 Docker 서비스 상태:
7

✅ 헬스체크 완료!
```

**해석**:
- ✅ 모든 서비스 정상
- HTTP 200: 성공 응답
- HTTP 301: 리다이렉트 (정상)
- 7개: 모든 서비스 실행 중

---

### 7️⃣ **ssh** - SSH 접속

원격 서버에 직접 접속합니다.

```bash
./server_control.sh ssh
```

**동작**:
- 원격 서버 셸 연결
- 작업 디렉토리로 이동
- 수동 명령어 실행 가능

**나가기**: `exit` 또는 `Ctrl+D`

**예제**:
```bash
# 접속
$ ./server_control.sh ssh

# 원격 서버에서 실행 가능
ubuntu@ip-172-26-1-134:/home/ubuntu/work_01/dongta-django/dongta-django$ docker ps

# 나가기
ubuntu@ip-172-26-1-134:~$ exit
```

---

### 8️⃣ **clean** - 정지된 컨테이너 정리

중지된 컨테이너와 고아 컨테이너를 제거합니다.

```bash
./server_control.sh clean
```

**동작**:
- 정지된 컨테이너 제거
- 고아 컨테이너 제거 (--remove-orphans)
- 사용하지 않는 네트워크 정리

**용도**:
- 디스크 공간 확보
- 정기 유지보수

**주의**: 이 명령어는 중지된 컨테이너를 영구 삭제합니다.

---

### 9️⃣ **rebuild** - 이미지 재빌드

Docker 이미지를 새로 빌드하고 시작합니다.

```bash
./server_control.sh rebuild
```

**동작**:
1. 이미지 재빌드 (--no-cache)
2. 서비스 시작
3. 상태 확인

**소요시간**: ~5-10분 (첫 빌드)

**용도**:
- 코드 변경 적용
- 의존성 업데이트
- 문제 해결

**주의**: 빌드 중에는 서비스가 중지됩니다.

---

## 🔄 자주 사용하는 조합

### **아침 체크** (서비스 시작)
```bash
./server_control.sh status          # 현재 상태 확인
./server_control.sh start           # 필요시 시작
./server_control.sh health-check    # 정상 작동 확인
```

### **로그 분석** (문제 해결)
```bash
./server_control.sh logs web        # 에러 확인
./server_control.sh status          # 서비스 상태
./server_control.sh restart         # 필요시 재시작
```

### **정기 유지보수** (주간)
```bash
./server_control.sh clean           # 정지된 컨테이너 정리
./server_control.sh status          # 최종 확인
./server_control.sh health-check    # 모든 서비스 점검
```

### **배포 후 검증** (새 코드)
```bash
./server_control.sh rebuild         # 이미지 재빌드
./server_control.sh logs web        # 시작 로그 확인
./server_control.sh health-check    # 서비스 정상 작동
```

---

## 🆘 문제 해결

### Q: SSH 연결이 안 됩니다
**A**: SSH 키 위치 확인
```bash
# 키 위치 확인
ls -la ~/Downloads/dongta_ver2.pem
ls -la ~/.ssh/dongta_ver2.pem

# 권한 확인
chmod 600 ~/Downloads/dongta_ver2.pem

# 수동 접속 테스트
ssh -i ~/Downloads/dongta_ver2.pem ubuntu@52.79.148.197
```

### Q: "command not found: ./server_control.sh"
**A**: 실행 권한 설정
```bash
chmod +x /Volumes/sk-p31/workspace/vibe_coding/work_01/server_control.sh
```

### Q: 서비스가 자꾸 중지됩니다
**A**: 로그 확인
```bash
./server_control.sh logs web
# 에러 메시지 확인 후 조치
```

### Q: 포트가 이미 사용 중입니다
**A**: 컨테이너 강제 정리
```bash
./server_control.sh stop
./server_control.sh clean
./server_control.sh start
```

---

## 📊 서비스 정보

| 서비스 | 포트 | 역할 |
|--------|------|------|
| **web** | 8000 | Django 애플리케이션 |
| **db** | 5432 | PostgreSQL 데이터베이스 |
| **redis** | 6379 | 캐시 및 메시지 큐 |
| **celery-sync** | - | 데이터 동기화 워커 (2개) |
| **celery-payment** | - | 결제 처리 워커 |
| **celery-beat** | - | 정기 작업 스케줄러 |

---

## ✅ 점검 목록

### 일일 점검
- [ ] `./server_control.sh status` - 모든 컨테이너 실행 중?
- [ ] `./server_control.sh health-check` - API 응답 정상?
- [ ] `./server_control.sh logs web` - 에러 없음?

### 주간 점검
- [ ] `./server_control.sh clean` - 정지된 컨테이너 정리?
- [ ] 로그 분석 - 성능 저하 없음?
- [ ] 보안 업데이트 확인

### 월간 점검
- [ ] 데이터베이스 백업
- [ ] Docker 이미지 업데이트
- [ ] 저장 공간 정리

---

## 📞 지원 정보

**서버 정보**:
- IP: 52.79.148.197
- User: ubuntu
- Key: ~/Downloads/dongta_ver2.pem
- Work Dir: /home/ubuntu/work_01/dongta-django/dongta-django

**웹사이트**:
- URL: https://dongta.theuit.info
- API: https://dongta.theuit.info/api/v1/
- Docs: https://dongta.theuit.info/api/docs/

---

**마지막 업데이트**: 2026-03-12
**상태**: ✅ 운영 중
