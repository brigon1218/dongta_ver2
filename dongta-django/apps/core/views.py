from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class LandingPageView(APIView):
    """
    GET / — 랜딩 페이지 (API 문서 및 서버 상태 확인)
    """
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        return Response({
            'title': '동타 플랫폼 (dongta.com)',
            'description': 'B2B 온라인 플랫폼 - 사업장 정보, 채용정보, 커뮤니티',
            'version': '2.0.0',
            'status': 'operational',
            'message': '장기간의 마이그레이션을 거쳐 Django 기반으로 전환되었습니다.',
            'api_endpoints': {
                'authentication': {
                    'description': '사용자 인증 및 권한 관리',
                    'endpoints': [
                        {'method': 'POST', 'path': '/api/v1/auth/signup/', 'description': '회원가입'},
                        {'method': 'POST', 'path': '/api/v1/auth/login/', 'description': '로그인'},
                        {'method': 'POST', 'path': '/api/v1/auth/logout/', 'description': '로그아웃'},
                        {'method': 'POST', 'path': '/api/v1/auth/refresh/', 'description': 'JWT 토큰 갱신'},
                    ]
                },
                'business114': {
                    'description': '사업장 정보 조회 및 관리',
                    'endpoints': [
                        {'method': 'GET', 'path': '/api/v1/business/', 'description': '사업장 목록 조회'},
                        {'method': 'POST', 'path': '/api/v1/business/', 'description': '사업장 등록'},
                        {'method': 'GET', 'path': '/api/v1/business/{id}/', 'description': '사업장 상세 조회'},
                        {'method': 'GET', 'path': '/api/v1/business/search/', 'description': '사업장 검색'},
                    ]
                },
                'recruitment': {
                    'description': '채용정보 및 이력서 관리',
                    'endpoints': [
                        {'method': 'GET', 'path': '/api/v1/recruit/', 'description': '채용공고 목록'},
                        {'method': 'POST', 'path': '/api/v1/recruit/', 'description': '채용공고 등록'},
                        {'method': 'GET', 'path': '/api/v1/recruit/{id}/', 'description': '공고 상세 조회'},
                    ]
                },
                'payment': {
                    'description': '포인트 충전 및 결제 관리',
                    'endpoints': [
                        {'method': 'GET', 'path': '/api/v1/payment/balance/', 'description': '포인트 잔액 조회', 'auth': True},
                        {'method': 'POST', 'path': '/api/v1/payment/charge/', 'description': '포인트 충전 요청', 'auth': True},
                        {'method': 'POST', 'path': '/api/v1/payment/use/', 'description': '포인트 차감', 'auth': True},
                        {'method': 'GET', 'path': '/api/v1/payment/history/', 'description': '결제 내역 조회', 'auth': True},
                    ]
                },
                'board': {
                    'description': '커뮤니티 게시판',
                    'endpoints': [
                        {'method': 'GET', 'path': '/api/v1/board/', 'description': '게시글 목록'},
                        {'method': 'POST', 'path': '/api/v1/board/', 'description': '게시글 작성', 'auth': True},
                        {'method': 'GET', 'path': '/api/v1/board/{id}/', 'description': '게시글 상세'},
                    ]
                },
            },
            'migration_info': {
                'legacy_system': 'PHP + MySQL (2004-2026)',
                'current_system': 'Django + PostgreSQL (2026-)',
                'database_sync': 'Celery를 통한 실시간 동기화',
                'deployment': {
                    'status': 'Production',
                    'container': 'Docker Compose',
                    'proxy': 'Nginx (HTTPS)',
                    'cache': 'Redis',
                    'cdn': 'Cloudflare',
                }
            },
            'documentation': {
                'api_docs': '/api/docs/',
                'schema': '/api/schema/',
                'github': 'https://github.com/brigon1218/dongta_ver2',
            },
            'features': {
                '사업장 정보': '114만개 이상의 국내 사업장 정보 제공',
                '채용 플랫폼': '채용공고 등록 및 이력서 관리',
                '커뮤니티': '산업별 정보 공유 게시판',
                '포인트 시스템': '서비스 이용 시 포인트 적립 및 사용',
                '모바일 지원': 'Responsive design으로 모든 디바이스 지원',
                'SSL 보안': 'Cloudflare Full Strict SSL 적용',
            },
            'contact': {
                'email': 'support@dongta.com',
                'phone': '02-XXXX-XXXX',
                'website': 'https://dongta.theuit.info',
            }
        }, status=status.HTTP_200_OK)
