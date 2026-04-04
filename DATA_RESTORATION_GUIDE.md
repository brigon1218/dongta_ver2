# MySQL 데이터 복원 가이드

## 상황

- **Django Admin UI**: django-jazzmin 설정 완료 ✅
- **데이터 상태**: 비어있음 (테스트 계정만 존재)
- **MySQL 백업**: 4개 파일 준비됨 (총 2.2GB)
- **목표**: 프로덕션 데이터로 복원

## 준비된 리소스

### 1. 백업 파일 위치
```
/Volumes/sk-p31/workspace/vibe_coding/work_01/dongta.mysql/
├── dongta_1022.sql (1.1GB) - 완전 덤프 ⭐
├── mysql_dongta_dump.sql (1.1GB) - 백업 복사본
├── mysql_data.tar.gz (428MB) - 압축 버전
└── create_user_db.txt (226B) - 계정 생성 스크립트
```

### 2. 생성된 관리 명령어
```
apps/accounts/management/commands/restore_mysql_data.py
```

**기능**:
- MySQL TBL_MEMB 테이블 읽기
- Django Member 모델로 매핑
- 비밀번호 해싱 (MD5 → bcrypt/argon2)
- 대량 삽입 (bulk_create)

**옵션**:
```bash
# 미리보기 (실제 저장 안 함)
python manage.py restore_mysql_data --dry-run

# 테스트 데이터 삭제 후 복원
python manage.py restore_mysql_data --clear

# 전체 복원
python manage.py restore_mysql_data
```

## 배포 단계

### Step 1: 서버에서 Docker 컨테이너 시작
```bash
ssh -i ~/.ssh/dongta_ver2.pem ubuntu@52.79.148.197
cd /home/ubuntu/work_01/dongta-django

# 이미지 빌드 (Jazzmin 포함)
docker-compose build web

# 컨테이너 시작
docker-compose up -d
```

### Step 2: 데이터 복원
```bash
# Django 쉘 진입
docker-compose exec -T web python manage.py shell

# 또는 직접 실행
docker-compose exec -T web python manage.py restore_mysql_data --dry-run
docker-compose exec -T web python manage.py restore_mysql_data --clear
```

### Step 3: 관리자 페이지 확인
```
https://dongta.theuit.info/admin
```

**예상 결과**:
- ✅ 전문적인 Jazzmin 테마 적용
- ✅ 프로덕션 회원 데이터 로드됨
- ✅ 아이콘 정상 표시
- ✅ 검색/필터 정상 작동

## Jazzmin 설정 사항

### 적용된 구성
```python
# config/settings/base.py의 JAZZMIN_SETTINGS:

- 사이트 제목: "dongta.com 관리자"
- 환영 메시지: 한국어 지원
- 탐색 메뉴:
  * 홈 (인덱스)
  * API 문서
  * 프론트엔드 링크
- 아이콘 매핑:
  * Member → 👔 (fas fa-user-tie)
  * Business → 🏪 (fas fa-store)
  * JobNotice → 💼 (fas fa-briefcase)
  * Payment → 💳 (fas fa-credit-card)
  * Post → 📰 (fas fa-newspaper)
  * Comment → 💬 (fas fa-comments)
```

## 데이터 매핑 (MySQL → Django)

| MySQL (TBL_MEMB) | Django (Member) | 설명 |
|---|---|---|
| memb_id | username | 아이디 |
| memb_name | name | 이름 |
| memb_email | email | 이메일 |
| memb_encrypt_passwd | password | 암호화된 비밀번호 |
| memb_level | level | 회원 등급 |
| memb_post1+2 | postal_code | 우편번호 |
| memb_addr1 | address | 주소 |
| memb_tel1+2+3 | landline | 일반전화 |
| memb_hp1+2+3 | phone | 휴대전화 |
| memb_corp | corp_name | 회사명 |
| memb_region | region | 지역 |
| memb_class | member_class | 회원분류 |
| memb_type | member_type | 회원유형 |
| memb_point | point | 포인트 |
| memb_regdate+regtime | created_at | 가입일시 |
| memb_ip | reg_ip | 가입IP |
| memb_logincount | login_count | 로그인 횟수 |
| memb_mailflag | email_opt_in | 이메일 수신동의 |
| memb_wantquitflag | want_quit | 탈퇴희망 |
| memb_abroadflag | is_overseas | 해외거주 |
| memb_abroadapplyflag | overseas_approved | 해외거주승인 |

## 주의사항

### 비밀번호 처리
- MySQL의 MD5 해시는 Django에서 검증 불가능
- 복원 후 사용자는 "비밀번호 찾기"로 초기화 필요
- 또는 기존 `memb_encrypt_passwd` 필드 사용 (있는 경우)

### 데이터 무결성
- 중복 아이디는 자동으로 스킵됨 (ignore_conflicts=True)
- NULL/빈 값은 자동으로 기본값으로 설정됨
- 첫 500명만 제한적으로 로드 (대용량 데이터셋 처리를 위함)

### 롤백
```bash
# 복원된 데이터 삭제
docker-compose exec -T web python manage.py shell

python manage.py shell
>>> from apps.accounts.models import Member
>>> # 테스트 계정만 삭제
>>> Member.objects.filter(username__in=['user1', 'user2', 'user3']).delete()
```

## 다음 단계

1. ✅ Jazzmin 설정 완료
2. ⏳ Docker 환경에서 데이터 복원
3. ⏳ 프로덕션 데이터 검증
4. ⏳ Business114, JobNotice 등 다른 모델 복원
5. ⏳ 성능 최적화 및 모니터링

## 문제 해결

### Admin 로그인 실패
```bash
# 관리자 계정 생성
docker-compose exec -T web python manage.py createsuperuser

# 또는 Django 쉘에서
docker-compose exec -T web python manage.py shell
>>> from apps.accounts.models import Member
>>> Member.objects.create_superuser('admin', 'admin@dongta.com', 'password123')
```

### 데이터 로드 오류
```bash
# 로그 확인
docker-compose logs -f web

# 마이그레이션 다시 실행
docker-compose exec -T web python manage.py migrate
```

### Jazzmin 아이콘 안 보임
```bash
# 정적 파일 수집
docker-compose exec -T web python manage.py collectstatic --noinput

# Nginx 캐시 초기화
docker-compose restart nginx
```

---

**상태**: 배포 준비 완료 ✅
**마지막 업데이트**: 2026-04-04
