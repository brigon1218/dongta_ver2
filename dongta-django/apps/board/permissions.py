from rest_framework import permissions
from .models import PostCategory


class IsStaffOrReadOnly(permissions.BasePermission):
    """
    Staff 사용자에게만 쓰기 권한을 허용 (공지사항 전용)
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class PostPermission(permissions.BasePermission):
    """
    게시글 카테고리 및 소유권에 따른 복합 권한 제어
    """
    def has_permission(self, request, view):
        # 목록 조회 및 상세 조회는 항상 허용
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # 생성 요청 시
        if request.method == 'POST':
            if not request.user or not request.user.is_authenticated:
                return False
            
            # 카테고리가 NOTICE인 경우 Staff만 가능
            category = request.data.get('category')
            if category == PostCategory.NOTICE:
                return request.user.is_staff
            return True
            
        return True

    def has_object_permission(self, request, view, obj):
        # 읽기 권한은 항상 허용
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # 수정/삭제는 본인만 가능 (IsOwner)
        return obj.member == request.user
