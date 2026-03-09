from rest_framework import serializers
from .models import Company, JobNotice, JobSeeker


class CompanySerializer(serializers.ModelSerializer):
    """채용 회사 시리얼라이저"""

    class Meta:
        model = Company
        fields = [
            'id', 'company_name', 'phone', 'email', 'homepage',
            'postal_code', 'address', 'introduction', 'has_notice',
            'created_at',
        ]
        read_only_fields = ['id', 'has_notice', 'created_at']


class JobNoticeSerializer(serializers.ModelSerializer):
    """채용공고 시리얼라이저"""
    company_name = serializers.CharField(source='company.company_name', read_only=True)
    member_username = serializers.CharField(source='member.username', read_only=True)

    class Meta:
        model = JobNotice
        fields = [
            'id', 'member', 'member_username', 'company', 'company_name',
            'employment_type', 'title', 'occupations', 'career_required',
            'is_approved', 'approval_no', 'payment_code',
            'is_premium', 'premium_start_date', 'premium_end_date',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'member', 'member_username', 'is_approved',
            'approval_no', 'is_premium', 'premium_start_date', 'premium_end_date',
            'created_at', 'updated_at',
        ]


class JobNoticeCreateSerializer(serializers.ModelSerializer):
    """채용공고 등록/수정용 시리얼라이저"""

    class Meta:
        model = JobNotice
        fields = [
            'company', 'employment_type', 'title', 'occupations',
            'career_required', 'payment_code',
        ]


class JobSeekerSerializer(serializers.ModelSerializer):
    """구직자 이력서 시리얼라이저"""
    member_username = serializers.CharField(source='member.username', read_only=True)

    class Meta:
        model = JobSeeker
        fields = [
            'id', 'member', 'member_username',
            'name', 'birth_date', 'gender', 'phone', 'email',
            'address', 'profile_image', 'resume_registered',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'member', 'member_username', 'created_at', 'updated_at']
