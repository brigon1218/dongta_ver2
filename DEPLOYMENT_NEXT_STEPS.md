# 🚀 dongta.com AWS 배포 - 다음 작업 지시

**상태**: PowerShell에서 Claude 재실행 준비
**날짜**: 2026-03-10
**진행률**: Phase 9 배포 중

---

## 📋 **현재 상황**

### ✅ 완료된 작업
- 마이그레이션 기능 구현 (94% Match Rate)
- Docker/docker-compose 설정
- Django 코드 완성
- 배포 가이드 및 스크립트 생성

### ⏳ 진행 중
- AWS EC2 배포 자동화

### ❌ 미해결 문제
- Bash 환경에서 SSH 접속 실패 (Windows 경로 인코딩 문제)
- 해결책: PowerShell에서 직접 실행

---

## 🎯 **즉시 실행할 작업 (PowerShell)**

### **Step 1: 코드 커밋 및 푸시**
```powershell
cd C:\Users\안용환\workspace\aws\vibe_coding\work_01\dongta_ver2

# 모든 변경사항 스테이징
git add -A

# 커밋 메시지 작성
git commit -m "Add password reset, social login, and deployment configs

- Password Reset API with email
- Social Login (Google/Naver OAuth2)
- Celery Beat Schedule configuration
- FRONTEND_URL environment variable
- Deployment script for AWS EC2
- Migration files for PasswordResetToken

Features completed with 94% Match Rate
Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

# 원격 저장소에 푸시
git push -u origin main
```

### **Step 2: AWS 서버 배포 실행**
```powershell
# PowerShell 관리자 권한으로 실행
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force

# 배포 스크립트 실행
.\deploy-aws.ps1
```

### **Step 3: 배포 후 환경 변수 설정**
```powershell
# 서버 접속
$key = "C:\Users\안용환\workspace\aws\vibe_coding\keystore\dongta_ver2.pem"
ssh -i $key ubuntu@52.79.148.197

# 서버에서 실행:
cd /home/ubuntu/work_01/dongta-django

# 환경 변수 파일 편집
nano .env.production

# 다음 값들을 실제 값으로 변경:
# SECRET_KEY=<실제 보안 키>
# EMAIL_HOST_USER=<이메일>
# EMAIL_HOST_PASSWORD=<앱 비밀번호>
# DANAL_MERCHANT_ID=<ID>
# DANAL_MERCHANT_KEY=<키>

# Ctrl+X → Y → Enter로 저장

# Django 재시작
docker-compose restart django

# 로그 확인
docker-compose logs -f django
```

---

## 📊 **배포 체크리스트**

- [ ] Git 커밋 및 푸시
- [ ] PowerShell에서 deploy-aws.ps1 실행
- [ ] 서버 접속 및 .env.production 수정
- [ ] Django 재시작
- [ ] 헬스 체크 (API 응답 확인)
- [ ] 관리자 페이지 접속 가능 확인
- [ ] 모니터링 설정

---

## 🌐 **배포 완료 후 접속 정보**

| URL | 설명 |
|-----|------|
| https://dongta.theuit.info | 메인 페이지 |
| https://dongta.theuit.info/admin/ | 관리자 페이지 |
| https://dongta.theuit.info/api/v1/ | API 엔드포인트 |

---

## 🔐 **필수 환경 변수 (서버에서 설정)**

```bash
# Django
SECRET_KEY=              # Django 보안 키
DEBUG=False             # 프로덕션 모드
ALLOWED_HOSTS=dongta.theuit.info,52.79.148.197

# Database
DATABASE_URL=postgresql://dongta:password@localhost:5432/dongtadb

# Email (Gmail)
EMAIL_HOST_USER=        # Gmail 이메일
EMAIL_HOST_PASSWORD=    # Gmail 앱 비밀번호

# Payment (Danal)
DANAL_MERCHANT_ID=      # 다날 ID
DANAL_MERCHANT_KEY=     # 다날 키

# Frontend
FRONTEND_URL=https://dongta.theuit.info
```

---

## 📞 **서버 정보**

- **IP**: 52.79.148.197
- **User**: ubuntu
- **Key**: C:\Users\안용환\workspace\aws\vibe_coding\keystore\dongta_ver2.pem
- **Work Dir**: /home/ubuntu/work_01
- **Domain**: dongta.theuit.info (Cloudflare SSL)

---

## 🚀 **다음 Phase**

배포 완료 후:
1. 모니터링 설정 (CloudWatch, Slack)
2. 백업 정책 수립
3. CI/CD 자동화 강화
4. 다음 기능 개발 시작

---

**마지막 진행 상황**:
- 마이그레이션: ✅ 완료 (94% Match Rate)
- 배포 스크립트: ✅ 생성 완료
- AWS 배포: ⏳ PowerShell에서 재실행 예정
