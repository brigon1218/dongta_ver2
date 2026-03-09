#!/bin/bash

# AWS EC2 배포 스크립트
# Phase 2: 하이브리드 연동 배포
# Usage: bash scripts/deploy-aws.sh

set -e

# AWS Server Configuration
SERVER_IP="52.79.148.197"
SERVER_USER="ubuntu"
SSH_KEY="/Users/yonghwanahn/workspace/vibe_coding/keystore/dongta-django.pem"
REMOTE_DIR="/home/ubuntu/work_01"
DOMAIN="dongta.theuit.info"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Phase 2 하이브리드 연동 배포 시작${NC}"
echo "Server: $SERVER_IP"
echo "Domain: $DOMAIN"
echo ""

# Step 1: 서버 연결 테스트
echo -e "${YELLOW}[1/7] 서버 연결 테스트...${NC}"
if ssh -i "$SSH_KEY" -o ConnectTimeout=5 "$SERVER_USER@$SERVER_IP" "echo 'OK'" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 서버 연결 성공${NC}"
else
    echo -e "${RED}✗ 서버 연결 실패${NC}"
    exit 1
fi

# Step 2: 필수 패키지 설치
echo -e "${YELLOW}[2/7] 필수 패키지 설치...${NC}"
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" << 'EOF'
sudo apt-get update
sudo apt-get install -y nginx python3-pip python3-venv git curl wget
echo "✓ 패키지 설치 완료"
EOF

# Step 3: 프로젝트 클론 (이미 있으면 업데이트)
echo -e "${YELLOW}[3/7] 최신 코드 동기화...${NC}"
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" << EOF
if [ ! -d "$REMOTE_DIR" ]; then
    git clone https://github.com/your-repo/dongta.git $REMOTE_DIR
else
    cd $REMOTE_DIR && git pull origin main
fi
echo "✓ 코드 동기화 완료"
EOF

# Step 4: Python 가상환경 및 의존성 설치
echo -e "${YELLOW}[4/7] Python 환경 및 의존성 설치...${NC}"
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" << EOF
cd $REMOTE_DIR
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements/production.txt
echo "✓ Python 환경 설정 완료"
EOF

# Step 5: Nginx 설정 복사
echo -e "${YELLOW}[5/7] Nginx 설정 적용...${NC}"
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" << EOF
cd $REMOTE_DIR

# Nginx 설정 복사
sudo cp config/nginx/nginx.conf /etc/nginx/nginx.conf
sudo cp -r config/nginx/conf.d/* /etc/nginx/conf.d/
sudo mkdir -p /etc/nginx/sites-enabled
sudo cp config/nginx/sites-enabled/* /etc/nginx/sites-enabled/

# 디렉토리 권한 설정
sudo chown -R www-data:www-data $REMOTE_DIR
sudo chmod -R 755 $REMOTE_DIR

# Nginx 설정 검증
sudo nginx -t

# Nginx 시작
sudo systemctl start nginx
sudo systemctl enable nginx

echo "✓ Nginx 설정 완료"
EOF

# Step 6: Systemd 서비스 설정
echo -e "${YELLOW}[6/7] Django Systemd 서비스 설정...${NC}"
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" << EOF
cd $REMOTE_DIR

# Systemd 파일 복사
sudo cp systemd/dongta-django.service /etc/systemd/system/
sudo cp systemd/dongta-django.socket /etc/systemd/system/

# 서비스 활성화
sudo systemctl daemon-reload
sudo systemctl start dongta-django.socket
sudo systemctl start dongta-django.service
sudo systemctl enable dongta-django.service

echo "✓ Systemd 서비스 설정 완료"
EOF

# Step 7: SSL 인증서 설치 (Let's Encrypt)
echo -e "${YELLOW}[7/7] SSL 인증서 설치...${NC}"
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" << EOF
# Certbot 설치
sudo apt-get install -y certbot python3-certbot-nginx

# 인증서 발급 (자동 Nginx 설정 포함)
sudo certbot certonly --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN

# Nginx 설정 업데이트 (SSL 경로 확인)
sudo systemctl reload nginx

# 자동 갱신 설정
sudo systemctl start certbot.timer
sudo systemctl enable certbot.timer

echo "✓ SSL 인증서 설치 완료"
EOF

# Step 8: 배포 검증
echo -e "${YELLOW}배포 검증 중...${NC}"
echo ""

# 헬스 체크 (HTTP)
echo -n "HTTP 헬스 체크: "
if curl -s "http://$DOMAIN/health" | grep -q '"status":"ok"'; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
fi

# Django API 체크 (HTTPS)
echo -n "Django API 체크: "
if timeout 3 curl -s -k "https://$DOMAIN/api/v1/health" | grep -q '"status"' 2>/dev/null; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo "⚠️  (아직 Django를 시작하지 않았을 수 있음)"
fi

# Nginx 상태
echo -n "Nginx 상태: "
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" sudo systemctl is-active nginx && echo -e "${GREEN}✓ Running${NC}" || echo -e "${RED}✗ Stopped${NC}"

# Django 서비스 상태
echo -n "Django 서비스 상태: "
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" sudo systemctl is-active dongta-django && echo -e "${GREEN}✓ Running${NC}" || echo -e "${RED}✗ Stopped${NC}"

echo ""
echo -e "${GREEN}🎉 Phase 2 하이브리드 연동 배포 완료!${NC}"
echo ""
echo "📊 배포 정보:"
echo "  서버: $SERVER_IP"
echo "  도메인: https://$DOMAIN"
echo "  API: https://$DOMAIN/api/v1/"
echo "  레거시 PHP: https://$DOMAIN/"
echo ""
echo "📝 다음 단계:"
echo "  1. Celery + Redis 환경 설정"
echo "  2. MySQL 트리거 작성"
echo "  3. Django Celery Task 구현"
echo ""
echo "🔧 서버 접근:"
echo "  ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP"
echo "  cd $REMOTE_DIR"
echo ""
echo "📋 유용한 명령어:"
echo "  # Nginx 재시작"
echo "  sudo systemctl restart nginx"
echo ""
echo "  # Django 로그 확인"
echo "  sudo journalctl -u dongta-django -f"
echo ""
echo "  # Nginx 접근 로그"
echo "  sudo tail -f /var/log/nginx/dongta_access.log"
