from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Admin 사용자만 접근 가능
    Phase 2.1: 모니터링 API용
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_staff
