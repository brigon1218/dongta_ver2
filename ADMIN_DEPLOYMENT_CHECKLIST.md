# Django Admin Jazzmin 배포 체크리스트

## ✅ 로컬 준비 완료

### 1. Jazzmin 설정
- ✅ `requirements/base.txt`에 `django-jazzmin>=3.0.0` 추가됨
- ✅ `config/settings/base.py`에 JAZZMIN_SETTINGS 추가됨
- ✅ INSTALLED_APPS에 'jazzmin' 등록 (admin 전에 위치)

### 2. 데이터 복원 명령어
- ✅ `apps/accounts/management/commands/restore_mysql_data.py` 생성됨
- ✅ MySQL TBL_MEMB → Django Member 자동 매핑
- ✅ --dry-run, --clear 옵션 지원

### 3. 백업 파일 확인
- ✅ `/Volumes/sk-p31/workspace/vibe_coding/work_01/dongta.mysql/dongta_1022.sql` (1.1GB)
- ✅ 회원 데이터 500개 가용

---

## 🚀 서버 배포 단계 (ubuntu@52.79.148.197)

### Phase 1: 코드 동기화
```bash
# 1. 서버 접속
ssh -i ~/Downloads/dongta_ver2.pem ubuntu@52.79.148.197

# 2. 작업 디렉토리로 이동
cd /home/ubuntu/work_01

# 3. 최신 코드 가져오기 (Git이 설정되어 있다면)
git pull origin main

# 또는 파일 수동 복사
scp -i ~/Downloads/dongta_ver2.pem \
  -r dongta-django/config/settings/base.py \
  ubuntu@52.79.148.197:/home/ubuntu/work_01/dongta-django/config/settings/

scp -i ~/Downloads/dongta_ver2.pem \
  dongta-django/requirements/base.txt \
  ubuntu@52.79.148.197:/home/ubuntu/work_01/dongta-django/requirements/

scp -i ~/Downloads/dongta_ver2.pem \
  -r dongta-django/apps/accounts/management \
  ubuntu@52.79.148.197:/home/ubuntu/work_01/dongta-django/apps/accounts/
```

### Phase 2: Docker 빌드 및 시작
```bash
# 1. 기존 컨테이너 중지
cd /home/ubuntu/work_01/dongta-django
docker-compose down

# 2. 이미지 빌드 (Jazzmin 포함)
docker-compose build web

# 3. 컨테이너 시작
docker-compose up -d

# 4. 로그 확인
docker-compose logs -f web | grep -E "(ERROR|Starting|Running)"
```

### Phase 3: 마이그레이션 및 데이터 복원
```bash
# 1. 마이그레이션 실행
docker-compose exec -T web python manage.py migrate

# 2. 정적 파일 수집
docker-compose exec -T web python manage.py collectstatic --noinput

# 3. 데이터 복원 (미리보기)
docker-compose exec -T web python manage.py restore_mysql_data --dry-run

# 4. 실제 복원
docker-compose exec -T web python manage.py restore_mysql_data

# 5. 복원된 데이터 확인
docker-compose exec -T web python manage.py shell << EOF
from apps.accounts.models import Member
print(f"총 회원 수: {Member.objects.count()}")
print(f"활성 회원: {Member.objects.filter(is_active=True).count()}")
print("\n최근 회원 5명:")
for m in Member.objects.order_by('-created_at')[:5]:
    print(f"  - {m.username} ({m.name}) - {m.email}")
EOF
```

### Phase 4: 관리자 계정 설정
```bash
# 1. 슈퍼유저 생성 (아직 없다면)
docker-compose exec -T web python manage.py createsuperuser

# 또는 Django 쉘에서 생성
docker-compose exec -T web python manage.py shell << EOF
from apps.accounts.models import Member
from django.contrib.auth.hashers import make_password

# 관리자 계정 확인
if not Member.objects.filter(username='admin').exists():
    admin = Member.objects.create_superuser(
        username='admin',
        email='admin@dongta.com',
        password='ChangeMe123!'
    )
    print(f"✅ 관리자 계정 생성: {admin.username}")
else:
    print("✅ 관리자 계정 이미 존재")
EOF
```

### Phase 5: 관리자 페이지 접근 테스트
```bash
# 1. URL 확인
# https://dongta.theuit.info/admin

# 2. 또는 로컬 테스트
curl -X GET http://localhost:8000/admin \
  -H "Host: dongta.theuit.info"

# 3. 로그 확인
docker-compose logs -f web | grep -E "(admin|jazzmin|200|500)"
```

---

## ✨ 예상 결과

### Admin Dashboard
```
✅ 전문적 UI (Jazzmin 테마)
✅ 회원 목록 (500+ 명)
✅ 아이콘 정상 표시 (💼 📰 💬 등)
✅ 검색/필터 정상 작동
✅ 네비게이션 메뉴:
   - 홈
   - API 문서
   - 프론트엔드 링크
```

### 데이터 표시
```
- 회원 (Member): 500명
- 활성 회원: ~450명
- 관리자: 1명
- 포인트 합계: 자동 집계
```

---

## 🔧 트러블슈팅

### 문제 1: "500 Server Error on Admin Login"
```bash
# 로그 확인
docker-compose logs web | tail -50

# 마이그레이션 상태 확인
docker-compose exec -T web python manage.py migrate --list

# 재실행
docker-compose exec -T web python manage.py migrate
```

### 문제 2: "Jazzmin 아이콘 안 보임"
```bash
# 정적 파일 재수집
docker-compose exec -T web python manage.py collectstatic --noinput --clear

# Nginx 재시작
docker-compose restart nginx
```

### 문제 3: "MySQL 데이터 복원 실패"
```bash
# 레거시 DB 연결 확인
docker-compose exec -T web python manage.py shell
>>> from django.db import connections
>>> cursor = connections['legacy'].cursor()
>>> cursor.execute("SELECT COUNT(*) FROM TBL_MEMB")
>>> print(cursor.fetchone())

# 또는 MySQL 직접 확인
mysql -h legacy_db_host -u root -p dongta -e "SELECT COUNT(*) FROM TBL_MEMB;"
```

### 문제 4: "비밀번호 재설정 필요"
```bash
# 사용자 비밀번호 초기화 방법
docker-compose exec -T web python manage.py shell << EOF
from apps.accounts.models import Member
from django.contrib.auth.hashers import make_password

user = Member.objects.get(username='user_id')
user.password = make_password('NewPassword123!')
user.save()
print(f"✅ {user.username}의 비밀번호 재설정 완료")
EOF
```

---

## 📋 완료 체크리스트

서버에서 실행할 때 아래 항목들을 확인하세요:

- [ ] 코드 동기화 완료
- [ ] Docker 이미지 빌드 성공
- [ ] 컨테이너 정상 시작
- [ ] 마이그레이션 성공
- [ ] 정적 파일 수집 완료
- [ ] 데이터 복원 완료
- [ ] 관리자 계정 생성
- [ ] Admin 페이지 접근 가능
- [ ] Jazzmin UI 정상 표시
- [ ] 회원 데이터 로드됨
- [ ] 검색/필터 작동
- [ ] 아이콘 정상 표시

---

## 📞 지원

문제가 발생하면:
1. 로그 확인: `docker-compose logs web`
2. 이 가이드의 트러블슈팅 섹션 참조
3. DATA_RESTORATION_GUIDE.md 확인

**마지막 업데이트**: 2026-04-04
