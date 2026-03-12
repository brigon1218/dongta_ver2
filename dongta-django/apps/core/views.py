from django.views.generic import TemplateView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class LandingPageView(TemplateView):
    """
    GET / — 랜딩 페이지 (HTML 템플릿)
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
