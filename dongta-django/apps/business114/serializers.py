from rest_framework import serializers
from .models import Business


class BusinessListSerializer(serializers.ModelSerializer):
    """업체 목록용 시리얼라이저 (경량)"""
    business_type_display = serializers.CharField(source='get_business_type_display', read_only=True)

    class Meta:
        model = Business
        fields = [
            'id', 'corp_name', 'phone', 'address',
            'industry_type', 'business_type', 'business_type_display',
            'items', 'keywords', 'view_count', 'is_approved',
            'logo_image', 'created_at',
        ]


class BusinessDetailSerializer(serializers.ModelSerializer):
    """업체 상세용 시리얼라이저 (전체 필드)"""
    member_username = serializers.CharField(source='member.username', read_only=True)
    business_type_display = serializers.CharField(source='get_business_type_display', read_only=True)

    class Meta:
        model = Business
        fields = [
            'id', 'member', 'member_username',
            'business_type', 'business_type_display',
            'corp_name', 'phone', 'fax', 'homepage',
            'postal_code', 'address',
            'industry_type', 'items', 'location_info',
            'keywords', 'description', 'logo_image',
            'view_count', 'total_payment', 'payment_method',
            'approval_no', 'is_approved',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'member', 'member_username',
            'view_count', 'total_payment', 'approval_no',
            'is_approved', 'created_at', 'updated_at',
        ]


class BusinessCreateSerializer(serializers.ModelSerializer):
    """업체 등록/수정용 시리얼라이저"""

    class Meta:
        model = Business
        fields = [
            'business_type', 'corp_name', 'phone', 'fax', 'homepage',
            'postal_code', 'address', 'industry_type', 'items',
            'location_info', 'keywords', 'description', 'logo_image',
            'payment_method',
        ]

    def validate_industry_type(self, value):
        if value not in range(0, 9):
            raise serializers.ValidationError('업종 코드는 0~8 사이여야 합니다.')
        return value
