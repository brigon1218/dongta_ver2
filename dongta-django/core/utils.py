from rest_framework.response import Response
from rest_framework import status


def success_response(data, http_status=status.HTTP_200_OK, meta=None):
    """표준 성공 응답"""
    response_data = {'success': True, 'data': data, 'error': None}
    if meta:
        response_data['meta'] = meta
    return Response(response_data, status=http_status)


def error_response(code, message, details=None, http_status=status.HTTP_400_BAD_REQUEST):
    """표준 에러 응답"""
    return Response({
        'success': False,
        'data': None,
        'error': {'code': code, 'message': message, 'details': details}
    }, status=http_status)
