from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from apps.accounts.models import Member


class UserProfileSerializer(serializers.ModelSerializer):
    """회원 프로필 조회 및 수정용 시리얼라이저"""
    class Meta:
        model = Member
        fields = [
            'id', 'username', 'name', 'email', 'phone', 'landline',
            'region', 'corp_name', 'postal_code', 'address',
            'member_type', 'member_class', 'point', 'last_login_at',
            'created_at'
        ]
        read_only_fields = ['id', 'username', 'point', 'last_login_at', 'created_at']


class PasswordChangeSerializer(serializers.Serializer):
    """비밀번호 변경용 시리얼라이저"""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class WithdrawalSerializer(serializers.Serializer):
    """회원 탈퇴용 시리얼라이저"""
    password = serializers.CharField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class ActivitySummarySerializer(serializers.Serializer):
    """내 활동 요약 정보를 담는 시리얼라이저"""
    posts_count = serializers.IntegerField()
    comments_count = serializers.IntegerField()
    businesses_count = serializers.IntegerField()
    job_notices_count = serializers.IntegerField()
