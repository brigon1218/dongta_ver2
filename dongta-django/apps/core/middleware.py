"""
dongta 커스텀 미들웨어
"""


class CacheHitHeaderMiddleware:
    """
    응답에 X-Cache-Hit 헤더를 추가하는 미들웨어
    - X-Cache-Hit: HIT  → 캐시에서 응답
    - X-Cache-Hit: MISS → 실제 뷰에서 응답

    django의 @cache_page는 캐시 히트 시 FetchedFromCacheMiddleware가
    응답을 반환하므로, 응답 헤더 유무로 구분 가능.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 요청 전: 캐시 히트 여부 마킹용 플래그 초기화
        request._cache_update_cache = True

        response = self.get_response(request)

        # 캐시 미들웨어가 히트한 경우: Django가 내부적으로 _cache_hit 속성 설정
        if getattr(response, '_cache_hit', False):
            response['X-Cache-Hit'] = 'HIT'
        else:
            response['X-Cache-Hit'] = 'MISS'

        return response
