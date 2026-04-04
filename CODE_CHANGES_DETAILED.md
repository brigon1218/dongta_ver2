# 코드 변경사항 상세 가이드

## 📝 수정된 파일

### 1. `dongta-django/config/settings/base.py`

**변경 위치**: Line 277-313 (원래 277-286)

**추가된 내용**:
```python
# =============================================================================
# Jazzmin (Django Admin UI)
# =============================================================================
JAZZMIN_SETTINGS = {
    "site_title": "dongta.com 관리자",
    "site_header": "dongta.com",
    "site_brand": "dongta",
    "welcome_sign": "dongta.com 관리자 페이지에 오신 것을 환영합니다",
    "copyright": "dongta.com 2024. 모든 권리 보유",
    "search_model": ["auth.User", "accounts.Member"],
    "topmenu_links": [
        {"name": "홈", "url": "admin:index", "permissions": ["auth.add_user"]},
        {"name": "API 문서", "url": "/api/schema/swagger/", "permissions": ["auth.add_user"]},
        {"name": "사이트", "url": "/", "new_window": True},
    ],
    "usermenu_links": [
        {
            "model": "accounts.member"
        }
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "accounts.Member": "fas fa-user-tie",
        "accounts.MemberDormant": "fas fa-user-slash",
        "accounts.PasswordResetToken": "fas fa-key",
        "business114.Business": "fas fa-store",
        "recruit.Company": "fas fa-building",
        "recruit.JobNotice": "fas fa-briefcase",
        "recruit.JobSeeker": "fas fa-user-graduate",
        "payment.PaymentHistory": "fas fa-credit-card",
        "board.Post": "fas fa-newspaper",
        "board.Comment": "fas fa-comments",
        "board.PostLike": "fas fa-thumbs-up",
    },
    "default_icon_parents": "fas fa-chevron-right",
    "default_icon_children": "fas fa-arrow-right",
    "show_ui_builder": False,
    "changeform_format": "single",
    "language_chooser": False,
}
```

**이유**:
- Jazzmin UI 커스터마이징
- 한국어 인터페이스 설정
- Font Awesome 아이콘 매핑
- Admin 메뉴 구성

**확인 방법**:
```bash
# Django settings 로드 확인
python manage.py shell
>>> from django.conf import settings
>>> settings.JAZZMIN_SETTINGS['site_title']
'dongta.com 관리자'
```

---

### 2. `dongta-django/requirements/base.txt`

**변경 위치**: Line 5

**추가된 내용**:
```
django-jazzmin>=3.0.0
```

**이미 있었나요?**
네, 파일을 확인해보니 이미 포함되어 있었습니다.
- Line 5: `django-jazzmin>=3.0.0`

---

### 3. `dongta-django/config/settings/base.py` (INSTALLED_APPS)

**변경 위치**: Line 32 (이미 설정됨)

**현재 상태**:
```python
DJANGO_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'jazzmin',  # ✅ Must come before django.contrib.admin
    'django.contrib.admin',  # jazzmin이 여기를 override함
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
```

**상태**: ✅ 이미 올바르게 설정됨

---

## 🆕 생성된 파일

### 1. `dongta-django/apps/accounts/management/__init__.py`
**목적**: Python 패키지 초기화
**내용**: 빈 파일

### 2. `dongta-django/apps/accounts/management/commands/__init__.py`
**목적**: Django management commands 패키지 초기화
**내용**: 빈 파일

### 3. `dongta-django/apps/accounts/management/commands/restore_mysql_data.py`
**목적**: MySQL 회원 데이터를 Django로 복원
**크기**: ~220줄
**주요 기능**:

#### 클래스 구조:
```python
class Command(BaseCommand):
    ├── handle()
    │   ├── MySQL 연결 확인
    │   ├── 기존 데이터 삭제 (--clear 옵션)
    │   └── _restore_members() 호출
    │
    ├── _restore_members()
    │   ├── SQL 쿼리 실행 (TBL_MEMB 읽기)
    │   ├── 각 행을 Member 객체로 매핑
    │   ├── Bulk insert
    │   └── 결과 리포팅
    │
    └── _map_row_to_member()
        ├── 필드 검증
        ├── 비밀번호 처리 (해싱)
        ├── 날짜 변환
        └── Member 객체 반환
```

#### 사용 예시:

**1) 미리보기 (실제 저장 안 함)**:
```bash
python manage.py restore_mysql_data --dry-run
```

출력 예시:
```
✓ MySQL 연결 성공. 회원 수: 2547

[DRY RUN] 500명의 회원을 복원할 예정:
  1. user123 (홍길동) - hong@example.com
  2. user456 (김철수) - kim@example.com
  ...
✓ 500명의 회원 데이터 복원 완료
```

**2) 테스트 데이터 제거 후 복원**:
```bash
python manage.py restore_mysql_data --clear
```

출력 예시:
```
✓ MySQL 연결 성공. 회원 수: 2547
⚠ 테스트 회원 데이터(user*) 삭제됨
✓ 500명의 회원 데이터 복원 완료
```

**3) 전체 복원**:
```bash
python manage.py restore_mysql_data
```

#### 데이터 매핑 상세:

| MySQL 필드 | Django 필드 | 변환 규칙 |
|---|---|---|
| memb_id | username | .strip() |
| memb_name | name | .strip()[:50] |
| memb_email | email | .strip() |
| memb_encrypt_passwd | password | 그대로 사용 (있으면) |
| memb_passwd | password | 없으면 make_password() |
| memb_level | level | 0→9, 1-3→1, 나머지→그대로 |
| memb_post1+2 | postal_code | f"{post1}{post2}"[:10] |
| memb_addr1 | address | [:200] 제한 |
| memb_tel1-3 | landline | f"{tel1}-{tel2}-{tel3}" |
| memb_hp1-3 | phone | f"{hp1}-{hp2}-{hp3}" |
| memb_corp | corp_name | [:100] 제한 |
| memb_region | region | [:50] 제한 |
| memb_class | member_class | [:20] 제한 |
| memb_type | member_type | [:20] 제한 |
| memb_point | point | int() 변환 |
| memb_regdate+regtime | created_at | datetime 병합 |
| memb_ip | reg_ip | [:45] (IPv6 지원) |
| memb_logincount | login_count | int() 변환 |
| memb_mailflag | email_opt_in | '0'이 아닌 경우 True |
| memb_wantquitflag | want_quit | '1'이면 True |
| memb_abroadflag | is_overseas | '1'이면 True |
| memb_abroadapplyflag | overseas_approved | '1'이면 True |

#### 에러 처리:
```python
# 자동 무시됨:
- NULL 필드 (기본값 사용)
- 빈 문자열 (빈값 유지)
- 이미 존재하는 아이디 (중복 방지)
- 데이터 타입 오류 (기본값 사용)

# 로깅됨:
- 모든 매핑 오류
- 마지막 10개 오류 출력
```

---

## 🔍 설정 옵션 상세 설명

### JAZZMIN_SETTINGS 각 항목:

```python
# 텍스트 설정
"site_title": "dongta.com 관리자"
  → 브라우저 탭 제목

"site_header": "dongta.com"
  → Admin 페이지 상단 헤더

"site_brand": "dongta"
  → 왼쪽 사이드바 브랜드명

"welcome_sign": "..."
  → 관리자 페이지 환영 메시지

"copyright": "..."
  → 페이지 하단 저작권

# 검색 설정
"search_model": ["auth.User", "accounts.Member"]
  → Admin 검색에 포함될 모델

# 메뉴 설정
"topmenu_links": [...]
  → 상단 메뉴 링크 (홈, API문서, 사이트)

"usermenu_links": [...]
  → 사용자 메뉴 (프로필 등)

# UI 설정
"show_sidebar": True
  → 왼쪽 네비게이션 메뉴 표시

"navigation_expanded": True
  → 네비게이션 기본 확장 상태

# 아이콘 설정
"icons": {...}
  → 모델별 Font Awesome 아이콘 매핑
  → fas fa-user-tie (회원)
  → fas fa-store (사업장)
  → fas fa-briefcase (채용정보)
  → fas fa-credit-card (결제)
  → fas fa-newspaper (게시판)
  → fas fa-comments (댓글)

"default_icon_parents": "fas fa-chevron-right"
  → 부모 메뉴 화살표 아이콘

"default_icon_children": "fas fa-arrow-right"
  → 하위 메뉴 화살표 아이콘

# 기능 설정
"show_ui_builder": False
  → UI 빌더 표시 안 함 (관리자 전용)

"changeform_format": "single"
  → 단일 탭 형식 (tabbed 대신)

"language_chooser": False
  → 언어 선택 버튼 숨김
```

---

## ✅ 검증 방법

### 1. Jazzmin 설치 확인:
```bash
python -m pip show django-jazzmin
# Name: django-jazzmin
# Version: 3.0.0 or higher
```

### 2. INSTALLED_APPS 순서 확인:
```bash
python manage.py shell
>>> from django.apps import apps
>>> app_names = [app.name for app in apps.get_app_configs()]
>>> jazzmin_idx = app_names.index('jazzmin')
>>> admin_idx = app_names.index('django.contrib.admin')
>>> jazzmin_idx < admin_idx  # True여야 함
True
```

### 3. 설정 로드 확인:
```bash
python manage.py shell
>>> from django.conf import settings
>>> list(settings.JAZZMIN_SETTINGS.keys())
['site_title', 'site_header', 'site_brand', 'welcome_sign', ...]
```

### 4. 관리 명령어 확인:
```bash
python manage.py help restore_mysql_data
```

---

## 📋 배포 체크리스트

- [ ] `requirements/base.txt`에서 django-jazzmin 버전 확인
- [ ] `config/settings/base.py`의 JAZZMIN_SETTINGS 확인
- [ ] `apps/accounts/management/` 디렉토리 생성 확인
- [ ] `restore_mysql_data.py` 파일 생성 확인
- [ ] Docker 이미지 빌드 시 에러 없음
- [ ] `python manage.py migrate` 성공
- [ ] `python manage.py collectstatic` 성공
- [ ] Admin 페이지 로드됨
- [ ] 아이콘 정상 표시됨
- [ ] `restore_mysql_data --dry-run` 실행 가능
- [ ] 회원 데이터 500명 이상 복원됨

---

**작성일**: 2026-04-04
**상태**: ✅ 로컬 완료, ⏳ 서버 배포 대기
