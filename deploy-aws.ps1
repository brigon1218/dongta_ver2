# AWS EC2 배포 PowerShell 스크립트
# 사용: PowerShell -ExecutionPolicy Bypass -File deploy-aws.ps1

$keyPath = "C:\Users\안용환\workspace\aws\vibe_coding\keystore\dongta_ver2.pem"
$serverIp = "52.79.148.197"
$serverUser = "ubuntu"
$workDir = "/home/ubuntu/work_01"

Write-Host "=========================================="
Write-Host "🚀 dongta.com AWS EC2 배포 시작" -ForegroundColor Green
Write-Host "=========================================="
Write-Host ""

# Step 1: 서버 접속 및 기본 확인
Write-Host "📁 Step 1: 서버 접속 및 디렉토리 확인" -ForegroundColor Cyan
ssh -i $keyPath $serverUser@$serverIp "cd $workDir && pwd && ls -la"

Write-Host ""
Write-Host "🔐 Step 2: 환경 변수 파일 생성" -ForegroundColor Cyan

# .env.production 내용
$envContent = @'
# Django Settings
SECRET_KEY=django-insecure-please-change-this-to-random-secret-key-in-production
DEBUG=False
ALLOWED_HOSTS=dongta.theuit.info,52.79.148.197,localhost

# Database
DATABASE_URL=postgresql://dongta:dongta_password@localhost:5432/dongtadb

# Redis
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=noreply@dongta.com

# Frontend
FRONTEND_URL=https://dongta.theuit.info

# Payment
DANAL_MERCHANT_ID=your_merchant_id
DANAL_MERCHANT_KEY=your_merchant_key
DANAL_RETURN_URL=https://dongta.theuit.info/api/v1/payment/danal/callback/

# JWT
JWT_ACCESS_LIFETIME_HOURS=1
JWT_REFRESH_LIFETIME_DAYS=7

# CORS
CORS_ALLOWED_ORIGINS=https://dongta.theuit.info,https://www.dongta.com

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1
'@

# 임시 파일로 저장 후 서버로 전송
$tempFile = "$env:TEMP\.env.production"
Set-Content -Path $tempFile -Value $envContent
scp -i $keyPath $tempFile $serverUser@$serverIp`:$workDir/dongta-django/.env.production
Remove-Item $tempFile
Write-Host "✅ .env.production 파일 전송 완료" -ForegroundColor Green

Write-Host ""
Write-Host "🐳 Step 3: Docker 빌드 및 배포" -ForegroundColor Cyan

# Docker 명령어들을 서버에서 실행
ssh -i $keyPath $serverUser@$serverIp @'
cd /home/ubuntu/work_01/dongta-django

# 기존 컨테이너 정리
echo "🧹 기존 컨테이너 정리..."
docker-compose down 2>/dev/null || true

# 이미지 빌드
echo "🔨 Docker 이미지 빌드 중..."
docker-compose build --no-cache

# 서비스 시작
echo "▶️  서비스 시작 중..."
docker-compose up -d postgres redis
sleep 10

docker-compose up -d django celery nginx
sleep 5

# 마이그레이션
echo "📊 데이터베이스 마이그레이션 중..."
docker-compose exec -T django python manage.py migrate

# 정적 파일 수집
echo "📦 정적 파일 수집 중..."
docker-compose exec -T django python manage.py collectstatic --noinput

echo "✅ 배포 완료!"
'@

Write-Host ""
Write-Host "🏥 Step 4: 서비스 상태 확인" -ForegroundColor Cyan
ssh -i $keyPath $serverUser@$serverIp "cd $workDir/dongta-django && docker-compose ps"

Write-Host ""
Write-Host "=========================================="
Write-Host "✅ 배포 완료!" -ForegroundColor Green
Write-Host "=========================================="
Write-Host ""
Write-Host "🌐 접속 정보:" -ForegroundColor Yellow
Write-Host "  - Frontend: https://dongta.theuit.info"
Write-Host "  - Admin: https://dongta.theuit.info/admin/"
Write-Host "  - API: https://dongta.theuit.info/api/v1/"
Write-Host ""
Write-Host "📝 다음 단계:" -ForegroundColor Yellow
Write-Host "  1. .env.production 파일에서 다음을 수정:"
Write-Host "     - SECRET_KEY"
Write-Host "     - EMAIL_HOST_USER / EMAIL_HOST_PASSWORD"
Write-Host "     - DANAL_MERCHANT_ID / DANAL_MERCHANT_KEY"
Write-Host ""
Write-Host "  2. 서버에서 수정 후 재시작:"
Write-Host "     ssh -i $keyPath $serverUser@$serverIp"
Write-Host "     cd $workDir/dongta-django"
Write-Host "     nano .env.production"
Write-Host "     docker-compose restart django"
Write-Host ""
