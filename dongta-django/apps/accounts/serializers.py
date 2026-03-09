from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import Member


class RegisterSerializer(serializers.ModelSerializer):
    """회원가입 시리얼라이저"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = Member
        fields = [
            'username', 'password', 'password_confirm',
            'name', 'email', 'phone', 'region', 'email_opt_in'
        ]

    def validate_username(self, value):
        if Member.objects.filter(username=value).exists():
            raise serializers.ValidationError('이미 사용 중인 아이디입니다.')
        return value

    def validate_email(self, value):
        if Member.objects.filter(email=value).exists():
            raise serializers.ValidationError('이미 사용 중인 이메일입니다.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password': '비밀번호가 일치하지 않습니다.'})
        return attrs

    def create(self, validated_data):
        return Member.objects.create_user(**validated_data)


class MemberSerializer(serializers.ModelSerializer):
    """회원 정보 조회/수정"""
    class Meta:
        model = Member
        fields = [
            'id', 'username', 'name', 'email', 'phone', 'landline',
            'postal_code', 'address', 'region', 'corp_name',
            'member_type', 'point', 'email_opt_in', 'is_overseas',
            'last_login_at', 'login_count', 'created_at',
        ]
        read_only_fields = ['id', 'username', 'point', 'last_login_at',
                            'login_count', 'created_at']


class PasswordChangeSerializer(serializers.Serializer):
    """비밀번호 변경"""
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password': '새 비밀번호가 일치하지 않습니다.'})
        return attrs

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('현재 비밀번호가 올바르지 않습니다.')
        return value
