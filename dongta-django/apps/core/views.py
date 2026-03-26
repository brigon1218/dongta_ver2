import django
from django.views.generic import TemplateView
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status


class LandingPageView(TemplateView):
    """
    GET / - 랜딩 페이지 (HTML 템플릿)
    """
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': '동타 플랫폼 (dongta.com)',
            'description': 'B2B 온라인 플랫폼 - 사업장 정보, 채용정보, 커뮤니티',
            'version': '2.0.0',
            'status': 'operational',
            'message': '장기간의 마이그레이션을 거쳐 Django 기반으로 전환되었습니다.',
        })
        return context


class HealthCheckView(APIView):
    """
    GET /api/v1/health/ - 헬스체크 엔드포인트
    - 인증 불필요 (로드밸런서, 모니터링 시스템에서 사용)
    - DB 및 Redis 연결 상태 포함
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        health_data = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '2.0.0',
            'django_version': django.VERSION,
            'checks': {},
        }
        overall_healthy = True

        # DB 연결 확인
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            health_data['checks']['database'] = 'ok'
        except Exception as e:
            health_data['checks']['database'] = f'error: {str(e)}'
            overall_healthy = False

        # Redis 연결 확인
        try:
            from django.core.cache import cache
            cache.set('health_check_probe', '1', timeout=5)
            result = cache.get('health_check_probe')
            health_data['checks']['cache'] = 'ok' if result == '1' else 'error: value mismatch'
            if result != '1':
                overall_healthy = False
        except Exception as e:
            health_data['checks']['cache'] = f'error: {str(e)}'
            overall_healthy = False

        if not overall_healthy:
            health_data['status'] = 'unhealthy'
            return Response(health_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(health_data, status=status.HTTP_200_OK)
