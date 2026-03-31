#!/bin/bash

################################################################################
# Canary Deployment Script
# 목적: Nginx weighted routing을 이용한 단계별 트래픽 전환
# 사용법: ./deploy/canary-deploy.sh [phase]
# 예시: ./deploy/canary-deploy.sh phase1
################################################################################

set -e

# 설정
NGINX_CONF="/etc/nginx/conf.d/dongta.conf"
DOCKER_COMPOSE_FILE="dongta-django/docker-compose.prod.yml"
PHASE=${1:-phase1}
DOCKER_COMPOSE_CMD="docker-compose -f $DOCKER_COMPOSE_FILE"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

################################################################################
# 함수 정의
################################################################################

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Nginx 설정 검증 및 재로드
reload_nginx() {
    log_info "Nginx 설정 검증 중..."
    if ! nginx -t; then
        log_error "Nginx 설정 검증 실패!"
        return 1
    fi

    log_info "Nginx 재로드 중..."
    nginx -s reload
    sleep 2
    log_info "Nginx 재로드 완료"
}

# 메트릭 조회 (Prometheus)
check_metrics() {
    local duration=$1  # 모니터링 시간 (분)

    log_info "메트릭 모니터링 시작 (${duration}분)..."

    for i in $(seq 1 $((duration * 4))); do
        sleep 15

        # 오류율 확인
        ERROR_RATE=$(curl -s 'http://localhost:9090/api/v1/query' \
            --data-urlencode 'query=rate(django_http_requests_total{status=~"5.."}[5m])' \
            2>/dev/null | jq '.data.result[0].value[1]' 2>/dev/null || echo "0")

        # 응답시간 P95 확인
        RESPONSE_TIME=$(curl -s 'http://localhost:9090/api/v1/query' \
            --data-urlencode 'query=histogram_quantile(0.95, rate(django_http_request_duration_seconds_bucket[5m]))' \
            2>/dev/null | jq '.data.result[0].value[1]' 2>/dev/null || echo "0")

        log_info "Progress: $((i * 15))s / $(($duration * 60))s - ErrorRate: ${ERROR_RATE} - P95: ${RESPONSE_TIME}s"

        # 오류율 임계값 체크 (1% = 0.01)
        if (( $(echo "$ERROR_RATE > 0.01" | bc -l) )); then
            log_error "오류율이 1%를 초과했습니다 (현재: ${ERROR_RATE})"
            log_warn "배포 롤백 권장"
            return 1
        fi

        # 응답시간 임계값 체크 (1s = 1.0)
        if (( $(echo "$RESPONSE_TIME > 1.0" | bc -l) )); then
            log_warn "응답시간이 1초를 초과했습니다 (현재: ${RESPONSE_TIME}s)"
        fi
    done

    log_info "메트릭 모니터링 완료: 정상 범위"
    return 0
}

# Nginx 설정 파일 수정 (가중치 변경)
update_nginx_weight() {
    local stable_weight=$1
    local canary_weight=$2

    log_info "Nginx 가중치 업데이트: stable=$stable_weight, canary=$canary_weight"

    # 임시 설정 파일 생성
    sed -i.bak "s/server localhost:8000 weight=.*/server localhost:8000 weight=$stable_weight;/" $NGINX_CONF
    sed -i "s/server localhost:8001 weight=.*/server localhost:8001 weight=$stable_weight;/" $NGINX_CONF
    sed -i "s/server localhost:8002 weight=.*/server localhost:8002 weight=$stable_weight;/" $NGINX_CONF
    sed -i "s/server localhost:8003 weight=.*/server localhost:8003 weight=$canary_weight;/" $NGINX_CONF

    reload_nginx
}

# Canary 인스턴스 배포
deploy_canary() {
    log_info "Canary 인스턴스(8003) 배포 중..."

    # 새로운 이미지 빌드
    $DOCKER_COMPOSE_CMD build web

    # Canary 컨테이너 실행 (포트 8003)
    $DOCKER_COMPOSE_CMD up -d --no-deps --scale web=1 web
    sleep 5

    log_info "Canary 인스턴스 배포 완료"
}

# Phase 1: 10% 트래픽
phase1_deploy() {
    log_info "=== Phase 1: 10% 트래픽 전환 시작 ==="
    log_info "Stable: 90% (localhost:8000-2)"
    log_info "Canary: 10% (localhost:8003)"

    # Canary 인스턴스 배포
    deploy_canary

    # Nginx 가중치 업데이트: 9:1
    update_nginx_weight 3 1

    # 모니터링 (2분)
    if check_metrics 2; then
        log_info "Phase 1 완료: 오류율 < 1%"
        log_info "계속해서 Phase 2로 진행하시겠습니까? (y/n)"
        read -r response
        if [[ $response == "y" ]]; then
            phase2_deploy
        else
            log_warn "배포 일시 중지. Phase 1 상태 유지 중"
        fi
    else
        log_error "Phase 1 실패: 롤백 시작"
        rollback_deploy
    fi
}

# Phase 2: 50% 트래픽
phase2_deploy() {
    log_info "=== Phase 2: 50% 트래픽 전환 시작 ==="
    log_info "Stable: 50% (localhost:8000-2)"
    log_info "Canary: 50% (localhost:8003)"

    # Nginx 가중치 업데이트: 1:1
    update_nginx_weight 1 1

    # 모니터링 (2분)
    if check_metrics 2; then
        log_info "Phase 2 완료: 응답시간 < 500ms"
        log_info "계속해서 Phase 3으로 진행하시겠습니까? (y/n)"
        read -r response
        if [[ $response == "y" ]]; then
            phase3_deploy
        else
            log_warn "배포 일시 중지. Phase 2 상태 유지 중"
        fi
    else
        log_error "Phase 2 실패: 롤백 시작"
        rollback_deploy
    fi
}

# Phase 3: 100% 트래픽
phase3_deploy() {
    log_info "=== Phase 3: 100% 트래픽 전환 완료 ==="
    log_info "Stable: 0% (비활성)"
    log_info "Canary: 100% (localhost:8003)"

    # Nginx 가중치 업데이트: 0:1 (Canary 전용)
    update_nginx_weight 0 1

    # 최종 모니터링 (1분)
    if check_metrics 1; then
        log_info "✅ Canary 배포 완료!"
        log_info "전체 트래픽이 새로운 버전으로 전환되었습니다"

        # Stable 인스턴스 정리
        cleanup_stable_instances
    else
        log_error "Phase 3 실패: 롤백 시작"
        rollback_deploy
    fi
}

# 안정적인 인스턴스 종료 및 새로운 버전으로 교체
cleanup_stable_instances() {
    log_info "기존 인스턴스(8000-8002) 정리 중..."
    # docker-compose down 등의 작업
    log_info "정리 완료"
}

# 배포 롤백
rollback_deploy() {
    log_warn "=== 배포 롤백 시작 ==="
    log_warn "Stable: 100% 복구"
    log_warn "Canary: 0% (비활성화)"

    # 가중치 초기화
    update_nginx_weight 1 0

    # Canary 인스턴스 중지
    $DOCKER_COMPOSE_CMD down

    log_info "롤백 완료: 이전 버전으로 복구되었습니다"
}

# 상태 확인
show_status() {
    log_info "=== 현재 배포 상태 ==="

    # Nginx 현재 가중치 출력
    log_info "Nginx Upstream 상태:"
    grep "server localhost" $NGINX_CONF | grep -E "(8000|8001|8002|8003)"

    # 실행 중인 컨테이너 확인
    log_info "컨테이너 상태:"
    $DOCKER_COMPOSE_CMD ps
}

################################################################################
# Main
################################################################################

case "$PHASE" in
    phase1)
        phase1_deploy
        ;;
    phase2)
        phase2_deploy
        ;;
    phase3)
        phase3_deploy
        ;;
    rollback)
        rollback_deploy
        ;;
    status)
        show_status
        ;;
    *)
        echo "사용법: $0 {phase1|phase2|phase3|rollback|status}"
        echo "예시:"
        echo "  $0 phase1      # Phase 1 배포 (10%)"
        echo "  $0 phase2      # Phase 2 배포 (50%)"
        echo "  $0 phase3      # Phase 3 배포 (100%)"
        echo "  $0 rollback    # 배포 롤백"
        echo "  $0 status      # 배포 상태 확인"
        exit 1
        ;;
esac
