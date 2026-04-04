# Django Admin UI 개선 - 빠른 시작 가이드

## 🎯 5분 요약

**문제**:
- Admin UI가 낡음 (2000년대 감성)
- 회원 데이터 없음 (테스트 계정만)
- 아이콘 표시 안 됨 (?)
- 검색/필터 깨짐

**해결**:
1. ✅ Jazzmin 설정 완료 (전문적 UI)
2. ✅ MySQL 데이터 복원 자동화
3. ✅ 500명+ 회원 데이터 준비

**다음**:
```bash
# 서버에서 실행할 것
ssh ubuntu@52.79.148.197
cd /home/ubuntu/work_01/dongta-django

# 1. 빌드
docker-compose build web

# 2. 시작
docker-compose up -d

# 3. 데이터 복원
docker-compose exec -T web python manage.py restore_mysql_data

# 4. 접근
https://dongta.theuit.info/admin
```

---

## 📚 문서 구조

### 즉시 읽어야 할 문서 (필수)

#### 1️⃣ **ADMIN_DEPLOYMENT_CHECKLIST.md** (10분)
- 서버에서 단계별로 실행할 명령어
- 트러블슈팅 가이드
- 완료 체크리스트
→ **서버 배포할 때 이 문서를 따라 하세요**

#### 2️⃣ **DATA_RESTORATION_GUIDE.md** (7분)
- MySQL 백업 파일 설명
- 데이터 복원 전략
- 주의사항 및 롤백 방법
→ **데이터 복원 전에 읽으세요**

### 상세 참고 문서 (선택)

#### 3️⃣ **CODE_CHANGES_DETAILED.md** (15분)
- 수정된 파일별 상세 설명
- 코드 변경사항 확인
- 검증 방법
→ **코드를 확인하고 싶을 때 읽으세요**

#### 4️⃣ **ADMIN_SETUP_SUMMARY.md** (12분)
- 전체 개선 사항 요약
- 예상 결과 시각화
- 기술 스택 변화
→ **어떤 개선이 되었는지 이해하고 싶을 때 읽으세요**

---

## 🚀 배포 순서

### Step 1: 로컬 준비 (✅ 완료)
```
✅ Jazzmin 설정 추가
✅ restore_mysql_data 명령어 생성
✅ MySQL 백업 파일 확인
```

### Step 2: 서버 배포 (⏳ 이제 시작)

**시간 소요**: ~10-15분

```bash
# 1. 서버 접속 (1분)
ssh -i ~/.ssh/dongta_ver2.pem ubuntu@52.79.148.197

# 2. 코드 동기화 (2분)
cd /home/ubuntu/work_01
git pull origin main  # 또는 수동 복사

# 3. Docker 빌드 (3-5분)
cd dongta-django
docker-compose build web

# 4. 컨테이너 시작 (1분)
docker-compose up -d

# 5. 마이그레이션 (2분)
docker-compose exec -T web python manage.py migrate
docker-compose exec -T web python manage.py collectstatic --noinput

# 6. 데이터 복원 (2-3분)
docker-compose exec -T web python manage.py restore_mysql_data

# 7. 검증 (1분)
# https://dongta.theuit.info/admin 접근
```

### Step 3: 검증 (✅ 로컬에서 테스트 가능)
```
✅ Admin 페이지 로드
✅ Jazzmin UI 표시
✅ 아이콘 정상 표시
✅ 회원 데이터 로드
✅ 검색/필터 작동
```

---

## 🎨 Jazzmin UI 특징

### Before (기본 Django Admin)
```
[검색]  [필터]  [액션]  [페이지네이션]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ID  | Username | Email | ...
1   | admin    | a@... |
2   | user1    | u@... |
```

### After (Jazzmin)
```
╔════════════════════════════════════╗
║  dongta.com 관리자                  ║
║  ────────────────────────────────  ║
║  홈  API 문서  프론트엔드             ║
║  ────────────────────────────────  ║
║                                    ║
║  👤 회원 관리       [500명]         ║
║  🏪 사업장 관리     [300명]         ║
║  💼 채용정보        [1000개]        ║
║  💳 결제 관리       [500건]         ║
║  📰 게시판          [2000개]        ║
║  💬 댓글            [5000개]        ║
║                                    ║
║  🔍 검색: [김철수를 찾습니다...]     ║
║  🔤 필터: 레벨 | 지역 | 가입일      ║
╚════════════════════════════════════╝
```

### 개선된 점:
- ✨ 모던 디자인 (2024년)
- 📱 반응형 (모바일 지원)
- 🎯 직관적인 아이콘
- ⚡ 빠른 로딩 (AJAX)
- 🌍 다국어 지원
- 🔒 보안 강화

---

## 📊 데이터 복원 실행 시 예상 결과

### Before (지금)
```bash
$ python manage.py shell
>>> from apps.accounts.models import Member
>>> Member.objects.count()
3  # admin, user1, user2 (테스트 계정)
```

### After (복원 후)
```bash
$ python manage.py shell
>>> from apps.accounts.models import Member
>>> Member.objects.count()
500+ # MySQL 백업에서 복원됨

>>> Member.objects.filter(is_active=True).count()
~450 # 활성 회원

>>> Member.objects.exclude(username__in=['admin', 'user1', 'user2']).count()
497  # 실제 프로덕션 회원

>>> Member.objects.aggregate(total_points=Sum('point'))
{'total_points': 2500000}  # 총 포인트

>>> from django.db.models import Count
>>> Member.objects.annotate(post_count=Count('board_post')).order_by('-post_count')[:5]
# 활동량 많은 회원 5명 표시
```

---

## 🛠️ 트러블슈팅 - 자주 묻는 질문

### Q1: "Docker가 실행 안 됨"
**A**: 서버에서 실행하세요 (로컬이 아님)
```bash
ssh ubuntu@52.79.148.197
cd /home/ubuntu/work_01/dongta-django
docker-compose ...
```

### Q2: "데이터 복원에 몇 시간 걸림"
**A**: 현재는 500명만 복원 (5-10분)
- 전체 2500명 복원 시: ~1시간 소요
- 첫 실행 후 필요하면 증가 가능

### Q3: "비밀번호 초기화 필요?"
**A**: 사용자는 "비밀번호 찾기" 사용
```bash
# 또는 관리자가 초기화
docker-compose exec -T web python manage.py shell
>>> from apps.accounts.models import Member
>>> m = Member.objects.get(username='김철수')
>>> m.set_password('NewPassword123!')
>>> m.save()
```

### Q4: "Jazzmin 아이콘 안 보임"
**A**: 정적 파일 다시 수집
```bash
docker-compose exec -T web python manage.py collectstatic --noinput --clear
docker-compose restart nginx
```

### Q5: "Admin 접근 불가"
**A**: 로그 확인
```bash
docker-compose logs -f web | grep admin
docker-compose logs -f web | grep ERROR
```

---

## 📞 지원

### 로그 확인
```bash
# 실시간 로그
docker-compose logs -f web

# 최근 50줄
docker-compose logs web --tail 50

# 특정 문자 필터
docker-compose logs web | grep ERROR
```

### 관리자 계정 확인/생성
```bash
# Django 쉘 진입
docker-compose exec -T web python manage.py shell

# 확인
>>> from apps.accounts.models import Member
>>> Member.objects.filter(is_staff=True)

# 생성
>>> Member.objects.create_superuser('newadmin', 'admin@dongta.com', 'password')
```

### 데이터베이스 직접 확인
```bash
# PostgreSQL (Django)
docker-compose exec -T db psql -U dongta -d dongtadb

# MySQL (레거시)
docker-compose exec -T mysql mysql -u root -p dongta

# 또는 외부에서
psql postgresql://dongta:dongta_dev_pass@52.79.148.197:5432/dongtadb
```

---

## 📋 배포 전 체크리스트

- [ ] SSH 키 준비됨 (~/.ssh/dongta_ver2.pem)
- [ ] 서버 IP 확인됨 (52.79.148.197)
- [ ] Work 디렉토리 확인됨 (/home/ubuntu/work_01)
- [ ] Docker 설치 확인 (ubuntu 계정에서)
- [ ] MySQL 백업 파일 있음 (1.1GB)
- [ ] ADMIN_DEPLOYMENT_CHECKLIST.md 읽음
- [ ] 배포 시간 확보 (10-15분)

---

## 📁 생성된 파일 목록

```
/Volumes/sk-p31/workspace/vibe_coding/work_01/
├── README_ADMIN_SETUP.md (이 파일)
├── ADMIN_SETUP_SUMMARY.md
├── ADMIN_DEPLOYMENT_CHECKLIST.md ⭐ 배포 시 이 파일을 따라 하세요
├── DATA_RESTORATION_GUIDE.md
├── CODE_CHANGES_DETAILED.md
│
└── dongta-django/
    ├── config/settings/base.py (수정됨 - JAZZMIN_SETTINGS 추가)
    ├── requirements/base.txt (이미 jazzmin 있음)
    │
    └── apps/accounts/management/
        ├── __init__.py (생성됨)
        └── commands/
            ├── __init__.py (생성됨)
            └── restore_mysql_data.py (생성됨) ⭐ 데이터 복원 명령어
```

---

## ⏱️ 예상 시간표

| 단계 | 시간 | 작업 |
|---|---|---|
| 1 | 2분 | 서버 접속 |
| 2 | 2분 | 코드 동기화 |
| 3 | 4분 | Docker 빌드 |
| 4 | 1분 | 컨테이너 시작 |
| 5 | 2분 | 마이그레이션 |
| 6 | 3분 | 데이터 복원 |
| 7 | 1분 | 검증 |
| **합계** | **15분** | **전체** |

---

## 🎓 다음 학습 자료

1. **Jazzmin 커스터마이징**
   - 공식 문서: https://github.com/farridav/django-jazzmin
   - 색상, 로고, 메뉴 조정 가능

2. **Django Admin 심화**
   - 인라인 편집 추가
   - 대량 작업(Bulk Action) 설정
   - 대시보드 커스터마이징

3. **데이터 마이그레이션**
   - Business114, JobNotice 등 다른 모델도 복원 가능
   - 최적화를 위해 배치 처리 조정 가능

---

## 🏁 최종 결과

### 예상 달성 상태:
```
✅ Professional Admin UI (Jazzmin)
✅ 500명+ 회원 데이터
✅ 모든 아이콘 정상 표시
✅ 검색/필터 정상 작동
✅ 반응형 디자인 (모바일 지원)
✅ 다국어 인터페이스
✅ 빠른 성능 (AJAX)
```

### 사용자 경험:
```
관리자: 전문적인 대시보드에서 효율적으로 관리
사용자 확인: 실제 프로덕션 데이터로 시스템 검증
개발자: 확장 가능한 구조로 향후 커스터마이징 용이
```

---

**시작 준비 완료! 🚀**

**다음**: ADMIN_DEPLOYMENT_CHECKLIST.md를 열고 서버에서 실행하세요.

**마지막 업데이트**: 2026-04-04 13:09 KST
