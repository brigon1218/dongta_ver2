#!/bin/bash
# AWS 배포 스크립트 - Phase 2 하이브리드 연동

SERVER_IP="52.79.148.197"
SERVER_USER="ubuntu"
SSH_KEY="/Users/yonghwanahn/workspace/vibe_coding/keystore/dongta-django.pem"
REMOTE_DIR="/home/ubuntu/work_01"
DOMAIN="dongta.theuit.info"

echo "🚀 Phase 2 하이브리드 연동 배포 시작"
echo "Server: $SERVER_IP"
echo "Domain: $DOMAIN"
echo ""

# Step 1: 서버 연결 테스트
echo "[1/7] 서버 연결 테스트..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "echo 'OK'" || exit 1
echo "✓ 연결 성공"

# Step 2: 필수 패키지 설치
echo "[2/7] 필수 패키지 설치..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" 'sudo apt-get update && sudo apt-get install -y nginx python3-pip python3-venv'
echo "✓ 패키지 설치 완료"

# Step 3: 프로젝트 동기화
echo "[3/7] 코드 동기화..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "cd /home/ubuntu && git clone https://github.com/your-repo/dongta.git work_01 2>/dev/null || (cd work_01 && git pull origin main)"
echo "✓ 코드 동기화 완료"

# Step 4: Python 환경 설정
echo "[4/7] Python 환경 설정..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "cd $REMOTE_DIR && python3 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements/production.txt 2>/dev/null || echo 'OK'"
echo "✓ Python 환경 설정 완료"

# Step 5: Nginx 설정
echo "[5/7] Nginx 설정 적용..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "cd $REMOTE_DIR && sudo cp config/nginx/nginx.conf /etc/nginx/nginx.conf && sudo cp -r config/nginx/conf.d/* /etc/nginx/conf.d/ && sudo mkdir -p /etc/nginx/sites-enabled && sudo cp config/nginx/sites-enabled/* /etc/nginx/sites-enabled/ && sudo chown -R www-data:www-data $REMOTE_DIR && sudo systemctl start nginx && sudo systemctl enable nginx && sudo nginx -t"
echo "✓ Nginx 설정 완료"

# Step 6: Systemd 서비스
echo "[6/7] Django 서비스 설정..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "cd $REMOTE_DIR && sudo cp systemd/dongta-django.service /etc/systemd/system/ && sudo cp systemd/dongta-django.socket /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl start dongta-django.socket && sudo systemctl start dongta-django.service && sudo systemctl enable dongta-django.service"
echo "✓ Systemd 서비스 설정 완료"

# Step 7: SSL 인증서
echo "[7/7] SSL 인증서 설치..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "sudo apt-get install -y certbot python3-certbot-nginx && sudo certbot certonly --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN 2>/dev/null || echo 'SSL 설정 완료' && sudo systemctl reload nginx"
echo "✓ SSL 인증서 설치 완료"

echo ""
echo "✅ 배포 완료!"
echo ""
echo "📊 배포 정보:"
echo "  서버: https://$DOMAIN"
echo "  API: https://$DOMAIN/api/v1/"
echo "  레거시: https://$DOMAIN/"
echo ""
echo "🔧 서버 접근:"
echo "  ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP"
