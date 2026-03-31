from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    작성자 본인만 수정/삭제 가능하도록 제한하는 권한 클래스
    객체는 'member' 필드를 가지고 있어야 함.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        return obj.member == request.user


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    객체 소유자에게만 쓰기 권한을 허용하고, 그 외에는 읽기 전용 권한만 허용
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return obj.member == request.user
