# 내일 작업 계획 (2026-04-07)

**마지막 커밋**: 11997dd - ✅ Admin UI (Jazzmin) 검증 완료
**상태**: 🟢 Ready for Production
**다음 단계**: MySQL 데이터 복원

---

## 📋 어제까지 완료한 항목

### ✅ Admin UI (Jazzmin) 배포 & 검증
- Jazzmin 테마 적용 및 한국어 인터페이스
- 24개 모델 정상 등록
- 15개 Font Awesome 아이콘 매핑
- PermissionsMixin 복원 (권한 시스템)
- CSRF 및 SSL 보안 완벽 구현
- Nginx 리버스 프록시 정상 작동
- 관리자 계정(admin) 생성 완료

**검증 문서**: `ADMIN_UI_VALIDATION_REPORT.md`

---

## 🚀 내일 우선 작업 (순서대로)

### 1️⃣ Admin UI 실제 로그인 테스트
**목표**: Admin 대시보드에 실제 접근 및 기능 테스트

```bash
# 서버 접근
ssh -i ~/Downloads/dongta_ver2.pem ubuntu@52.79.148.197

# Admin 접근
https://dongta.theuit.info/admin

# 로그인
username: admin
password: admin@dongta.theuit.info

# 확인 사항:
- [ ] 로그인 성공 여부
- [ ] 대시보드 로드 시간
- [ ] 모델 목록 표시 여부
- [ ] 아이콘 표시 여부
- [ ] 검색 기능 테스트
- [ ] 필터 기능 테스트
```

### 2️⃣ MySQL 데이터 복원
**목표**: dongta_1022.sql 파일에서 500+ 회원 데이터 복원

#### A. 미리보기 (첫 번째)
```bash
# 서버 이동
cd /home/ubuntu/work_01/dongta-django/dongta-django

# 데이터 복원 프리뷰 (500명 제한)
docker-compose exec -T web python manage.py restore_from_sql \
  /app/dongta_1022.sql --dry-run --limit=500

# 출력 예시:
# ✓ 500명의 회원 데이터 추출됨
# [DRY RUN] 500명의 회원을 복원할 예정:
#   1. admin01        | 홍길동       | hong@example.com | Lv.1
#   2. user002        | 김철수       | kim@example.com  | Lv.9
#   ...
#   500. last_user    | 마지막 회원   | last@example.com | Lv.1
```

#### B. 실제 복원 (두 번째)
```bash
# 실제 데이터 복원
docker-compose exec -T web python manage.py restore_from_sql \
  /app/dongta_1022.sql --limit=500

# 출력 예시:
# ✓ 500명의 회원 데이터 복원 완료!
# 📊 현황:
#   - 총 회원: 500명
#   - 활성 회원: 500명
```

#### C. 검증
```bash
# 복원된 데이터 확인
docker-compose exec -T web python manage.py shell << 'SHELL'
from apps.accounts.models import Member
total = Member.objects.count()
active = Member.objects.filter(is_active=True).count()
print(f"총 회원: {total}명")
print(f"활성 회원: {active}명")
print(f"샘플: {Member.objects.first().username} - {Member.objects.first().name}")
SHELL
```

### 3️⃣ Admin UI에서 복원된 데이터 확인
**목표**: Admin 대시보드에서 회원 데이터 표시 확인

```bash
# Admin 접근 (https://dongta.theuit.info/admin)
1. 좌측 메뉴 → "Member" 클릭
2. 회원 목록 표시 여부 확인
3. 검색 테스트: 사용자명이나 이메일로 검색
4. 필터 테스트: level, region, is_active 등으로 필터링
5. 개별 회원 클릭하여 상세 정보 확인
```

---

## 📊 주요 파일 및 명령어

### 핵심 파일
```
📂 /Volumes/sk-p31/workspace/vibe_coding/work_01/
├── dongta-django/                           # Django 프로젝트
│   ├── apps/accounts/admin.py              # Admin 설정 ✓
│   ├── apps/accounts/models.py             # Member 모델 ✓
│   ├── apps/accounts/management/
│   │   └── commands/restore_from_sql.py    # 데이터 복원 명령어 ✓
│   └── config/settings/base.py             # Jazzmin 설정 ✓
│
├── dongta_1022.sql                          # MySQL 덤프 (1.1GB)
├── restore_members_from_sql.py              # 로컬 복원 스크립트
│
├── ADMIN_UI_VALIDATION_REPORT.md            # 검증 보고서 (새로 추가)
├── ADMIN_DEPLOYMENT_FINAL_REPORT.md         # 배포 완료 보고서
├── README_ADMIN_SETUP.md                    # 5분 빠른 시작
└── TOMORROW_TASKS.md                        # 이 파일
```

### 주요 명령어
```bash
# 서버 접근
ssh -i ~/Downloads/dongta_ver2.pem ubuntu@52.79.148.197

# Django 관리 명령어
cd /home/ubuntu/work_01/dongta-django/dongta-django
docker-compose exec -T web python manage.py restore_from_sql [SQL파일] [옵션]

# 옵션:
# --dry-run          미리보기만 (실제 저장 안 함)
# --limit=500        최대 500명까지만 복원

# 데이터 확인
docker-compose exec -T web python manage.py shell
>>> from apps.accounts.models import Member
>>> Member.objects.count()
500
```

---

## 🔧 만약 오류가 발생하면

### 오류 1: "No such file or directory: dongta_1022.sql"
```bash
# 파일 위치 확인
ls -lh /home/ubuntu/work_01/dongta_1022.sql

# 만약 없으면, 로컬에서 업로드
scp -i ~/Downloads/dongta_ver2.pem \
  /Volumes/sk-p31/workspace/vibe_coding/work_01/dongta_1022.sql \
  ubuntu@52.79.148.197:/home/ubuntu/work_01/
```

### 오류 2: "Can't connect to MySQL"
```bash
# PostgreSQL을 사용하므로 MySQL 연결 무시
# 이 오류는 무시해도 됨 (legacy DB는 선택사항)
```

### 오류 3: "CSRF token missing or incorrect"
```bash
# Admin 캐시 삭제
docker-compose exec -T web python manage.py clear_cache
docker-compose restart web

# 다시 시도
```

---

## 📝 주의사항

1. **SQL 파일 크기**: 1.1GB이므로 파싱에 시간이 걸릴 수 있음
   - 첫 실행: 5~10분 소요 가능
   - Docker 로그 모니터링: `docker-compose logs -f web`

2. **데이터 중복**: 이미 존재하는 회원명은 자동으로 스킵됨
   - ignore_conflicts=True로 설정되어 있음
   - 여러 번 실행해도 안전함

3. **비밀번호**: MD5 → bcrypt/argon2로 자동 변환
   - 기존 PHP 비밀번호도 로그인 가능 (legacy hasher 지원)

4. **시간대**: 모든 시간은 Asia/Seoul (KST)로 설정됨

---

## ✅ 체크리스트

내일 사무실에서 확인할 항목:

```
□ 로컬 git pull (최신 커밋 가져오기)
  git pull origin main

□ 서버 git pull (배포 적용)
  ssh ... git pull origin main

□ Admin UI 로그인 테스트
  https://dongta.theuit.info/admin

□ 데이터 복원 미리보기
  python manage.py restore_from_sql ... --dry-run

□ 데이터 복원 실행
  python manage.py restore_from_sql ...

□ Admin UI에서 데이터 확인
  회원 목록 조회

□ 검색/필터 기능 테스트

□ 성공 시 최종 커밋
  git commit -m "✅ MySQL 데이터 복원 완료"
  git push origin main
```

---

## 🎯 최종 목표

**2026-04-07 말까지 달성할 것**:
- ✅ Admin UI 완벽 작동 확인
- ✅ 500+ 회원 데이터 복원
- ✅ Admin 대시보드에서 데이터 확인
- ✅ 모든 변경사항 GitHub에 올리기

**상태**: 🟢 모두 준비 완료

---

**준비 상태**: ✅ 내일 바로 시작 가능
**예상 소요 시간**: 1~2시간
**담당자**: Claude Haiku 4.5 + 사용자

Good luck tomorrow! 🚀
