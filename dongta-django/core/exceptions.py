from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """표준 에러 응답 형식으로 변환"""
    response = exception_handler(exc, context)

    if response is not None:
        error_code = getattr(exc, 'code', 'ERROR')
        if hasattr(exc, 'detail'):
            if isinstance(exc.detail, dict):
                message = '입력값이 올바르지 않습니다.'
                details = exc.detail
            elif isinstance(exc.detail, list):
                message = str(exc.detail[0]) if exc.detail else '오류가 발생했습니다.'
                details = None
            else:
                message = str(exc.detail)
                details = None
        else:
            message = str(exc)
            details = None

        response.data = {
            'success': False,
            'data': None,
            'error': {
                'code': error_code,
                'message': message,
                'details': details,
            }
        }
    else:
        # 처리되지 않은 예외 (500)
        logger.exception('Unhandled exception', exc_info=exc)
        response = Response({
            'success': False,
            'data': None,
            'error': {
                'code': 'SERVER_ERR',
                'message': '서버 오류가 발생했습니다.',
                'details': None,
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response
