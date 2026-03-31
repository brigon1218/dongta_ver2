#!/bin/bash

################################################################################
# Dongta Server Control Script
# 원격 서버의 Docker 서비스를 일괄 관리하는 스크립트
################################################################################

# 설정
SERVER_IP="52.79.148.197"
SERVER_USER="ubuntu"
SSH_KEY="${HOME}/Downloads/dongta_ver2.pem"
WORK_DIR="/home/ubuntu/work_01/dongta-django/dongta-django"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수: 도움말 출력
print_help() {
    cat << 'EOF'
╔════════════════════════════════════════════════════════════════════╗
║           Dongta Server Control Script v1.0                       ║
║                                                                    ║
║  사용법: ./server_control.sh [명령어]                              ║
║                                                                    ║
║  명령어:                                                           ║
║  ────────────────────────────────────────────────────────────    ║
║  start         - 서버 시작 (모든 Docker 서비스)                   ║
║  stop          - 서버 중지 (모든 Docker 서비스)                   ║
║  restart       - 서버 재시작                                      ║
║  status        - 서버 상태 확인                                   ║
║  logs [service]- 서비스 로그 확인 (기본: web)                     ║
║  ssh           - 서버에 SSH 접속                                  ║
║  health-check  - 웹사이트 헬스체크                                ║
║  clean         - 정지된 컨테이너 정리                             ║
║  rebuild       - 이미지 재빌드 및 시작                           ║
║  help          - 이 도움말 출력                                   ║
║                                                                    ║
║  예제:                                                             ║
║  ────────────────────────────────────────────────────────────    ║
║  ./server_control.sh start           # 서버 시작                  ║
║  ./server_control.sh logs web        # Django 로그 확인           ║
║  ./server_control.sh health-check    # 웹사이트 테스트            ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
EOF
}

# 함수: SSH 명령 실행
run_ssh_command() {
    local cmd="$1"
    ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "cd $WORK_DIR && $cmd"
}

# 함수: 서버 상태 확인
check_status() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}📊 Docker 컨테이너 상태${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    run_ssh_command "docker-compose ps"
    echo ""
}

# 함수: 서버 시작
start_server() {
    echo -e "${GREEN}🚀 서버 시작 중...${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"

    run_ssh_command "docker-compose up -d"

    echo -e "${GREEN}✅ 서버 시작 완료!${NC}"
    sleep 2
    check_status
}

# 함수: 서버 중지
stop_server() {
    echo -e "${YELLOW}⏹️  서버 중지 중...${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"

    run_ssh_command "docker-compose down"

    echo -e "${GREEN}✅ 서버 중지 완료!${NC}"
    sleep 1
    check_status
}

# 함수: 서버 재시작
restart_server() {
    echo -e "${YELLOW}🔄 서버 재시작 중...${NC}"

    stop_server
    echo ""
    start_server

    echo -e "${GREEN}✅ 서버 재시작 완료!${NC}"
}

# 함수: 로그 확인
show_logs() {
    local service="${1:-web}"
    echo -e "${BLUE}📋 ${service} 서비스 로그 (최근 50줄)${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    run_ssh_command "docker-compose logs --tail=50 $service"
}

# 함수: SSH 접속
ssh_connect() {
    echo -e "${BLUE}🔗 원격 서버에 접속 중...${NC}"
    echo -e "${BLUE}나가기: exit 또는 Ctrl+D${NC}"
    echo ""
    ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_IP" "cd $WORK_DIR && bash"
}

# 함수: 헬스체크
health_check() {
    echo -e "${BLUE}🏥 헬스체크 실행 중...${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"

    local domain="https://dongta.theuit.info"

    # 1. 웹사이트 응답
    echo -n "🌐 메인 페이지: "
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -m 10 "$domain/" 2>/dev/null)
    if [ "$http_code" = "301" ] || [ "$http_code" = "302" ]; then
        echo -e "${GREEN}✅ HTTP $http_code (리다이렉트)${NC}"
    elif [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✅ HTTP $http_code${NC}"
    else
        echo -e "${RED}❌ HTTP $http_code${NC}"
    fi

    # 2. API 응답
    echo -n "🏢 Business API: "
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -m 10 "$domain/api/v1/business/" 2>/dev/null)
    if [ "$http_code" = "200" ] || [ "$http_code" = "301" ]; then
        echo -e "${GREEN}✅ HTTP $http_code${NC}"
    else
        echo -e "${RED}❌ HTTP $http_code${NC}"
    fi

    # 3. API Docs
    echo -n "📚 API Docs: "
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -m 10 "$domain/api/docs/" 2>/dev/null)
    if [ "$http_code" = "200" ] || [ "$http_code" = "301" ]; then
        echo -e "${GREEN}✅ HTTP $http_code${NC}"
    else
        echo -e "${RED}❌ HTTP $http_code${NC}"
    fi

    # 4. 서버 상태
    echo ""
    echo -e "${BLUE}📊 Docker 서비스 상태:${NC}"
    run_ssh_command "docker-compose ps --status running | wc -l"

    echo -e "${GREEN}✅ 헬스체크 완료!${NC}"
}

# 함수: 정지된 컨테이너 정리
clean_containers() {
    echo -e "${YELLOW}🧹 정지된 컨테이너 정리 중...${NC}"
    run_ssh_command "docker-compose down --remove-orphans"
    echo -e "${GREEN}✅ 정리 완료!${NC}"
}

# 함수: 이미지 재빌드
rebuild_images() {
    echo -e "${YELLOW}🔨 Docker 이미지 재빌드 중...${NC}"
    echo -e "${BLUE}이 작업은 5-10분 소요될 수 있습니다.${NC}"
    echo ""

    run_ssh_command "docker-compose build --no-cache && docker-compose up -d"

    echo -e "${GREEN}✅ 재빌드 완료!${NC}"
    sleep 2
    check_status
}

# 함수: SSH 키 확인
check_ssh_key() {
    if [ ! -f "$SSH_KEY" ]; then
        echo -e "${RED}❌ SSH 키를 찾을 수 없습니다: $SSH_KEY${NC}"
        echo -e "${YELLOW}다른 위치를 시도 중...${NC}"

        # 다른 경로 시도
        if [ -f "${HOME}/.ssh/dongta_ver2.pem" ]; then
            SSH_KEY="${HOME}/.ssh/dongta_ver2.pem"
            echo -e "${GREEN}✅ SSH 키 발견: $SSH_KEY${NC}"
        else
            echo -e "${RED}❌ SSH 키를 찾을 수 없습니다.${NC}"
            echo "위치 확인:"
            echo "  1. ~/Downloads/dongta_ver2.pem"
            echo "  2. ~/.ssh/dongta_ver2.pem"
            exit 1
        fi
    fi
}

# 메인 로직
main() {
    local command="${1:-help}"

    # SSH 키 확인 (help 제외)
    if [ "$command" != "help" ]; then
        check_ssh_key
    fi

    case "$command" in
        start)
            start_server
            ;;
        stop)
            stop_server
            ;;
        restart)
            restart_server
            ;;
        status)
            check_status
            ;;
        logs)
            show_logs "${2:-web}"
            ;;
        ssh)
            ssh_connect
            ;;
        health-check)
            health_check
            ;;
        clean)
            clean_containers
            ;;
        rebuild)
            rebuild_images
            ;;
        help|--help|-h)
            print_help
            ;;
        *)
            echo -e "${RED}❌ 알 수 없는 명령어: $command${NC}"
            echo ""
            print_help
            exit 1
            ;;
    esac
}

# 스크립트 실행
main "$@"
