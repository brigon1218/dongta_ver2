import django
from django.views.generic import TemplateView
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
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


@method_decorator(staff_member_required, name='dispatch')
class AdminDashboardStatsView(APIView):
    """
    GET /admin/dashboard-stats/
    관리자 대시보드 통계 API (is_staff=True 필요)
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        from datetime import date
        today = date.today()
        stats = {}

        # 회원/사업장 통계
        try:
            from apps.accounts.models import Member
            from apps.business114.models import Business
            stats['users'] = {
                'total': Member.objects.count(),
                'today_new': Member.objects.filter(created_at__date=today).count(),
                'active': Member.objects.filter(is_active=True).count(),
            }
            stats['businesses'] = {
                'total': Business.objects.count(),
                'pending_approval': Business.objects.filter(is_approved=False).count(),
            }
        except Exception:
            stats['users'] = {'total': 'N/A', 'today_new': 'N/A'}
            stats['businesses'] = {'total': 'N/A', 'pending_approval': 'N/A'}

        # 결제 통계
        try:
            from django.db.models import Sum, Count
            from apps.payment.models import PaymentHistory
            agg = PaymentHistory.objects.filter(created_at__date=today).aggregate(
                count=Count('id'),
                amount=Sum('amount'),
            )
            stats['payments'] = {
                'today_count': agg['count'] or 0,
                'today_amount': int(agg['amount'] or 0),
            }
        except Exception:
            stats['payments'] = {'today_count': 'N/A', 'today_amount': 'N/A'}

        # 게시판 통계
        try:
            from apps.board.models import Post
            stats['posts'] = {
                'total': Post.objects.count(),
                'today_new': Post.objects.filter(created_at__date=today).count(),
            }
        except Exception:
            stats['posts'] = {'total': 'N/A', 'today_new': 'N/A'}

        # 시스템 상태 (HealthCheckView 로직 재사용)
        system = {}
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            system['database'] = 'ok'
        except Exception:
            system['database'] = 'error'

        try:
            from django.core.cache import cache
            cache.set('admin_stats_probe', '1', timeout=5)
            system['cache'] = 'ok' if cache.get('admin_stats_probe') == '1' else 'error'
        except Exception:
            system['cache'] = 'error'

        try:
            from celery.app.control import Control
            from config.celery import app as celery_app
            inspector = celery_app.control.inspect(timeout=1.0)
            active = inspector.active()
            system['celery'] = 'ok' if active is not None else 'error'
        except Exception:
            system['celery'] = 'N/A'

        stats['system'] = system
        return Response(stats, status=status.HTTP_200_OK)
