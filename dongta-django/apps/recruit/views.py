from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from core.utils import success_response, error_response
from .models import Company, JobNotice, JobSeeker
from .serializers import (
    CompanySerializer,
    JobNoticeSerializer,
    JobNoticeCreateSerializer,
    JobSeekerSerializer,
)
from .permissions import IsOwner, IsOwnerOrReadOnly
from .services import RecruitService


class CompanyViewSet(viewsets.ModelViewSet):
    """
    회사 정보 관리 ViewSet
    """
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Company.objects.filter(member=self.request.user, is_deleted=False)

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return success_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return success_response(serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response(serializer.data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success_response(serializer.data)


class JobNoticeViewSet(viewsets.ModelViewSet):
    """
    채용 공고 관리 ViewSet
    """
    permission_classes = [IsOwnerOrReadOnly]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return JobNoticeCreateSerializer
        return JobNoticeSerializer

    def get_queryset(self):
        queryset = JobNotice.objects.filter(is_deleted=False).select_related('company', 'member')
        
        # 목록 조회 시에는 승인된 것만 (단, 본인 공고는 미승인 상태도 조회 가능)
        if self.action == 'list':
            user = self.request.user
            if user.is_authenticated:
                queryset = queryset.filter(Q(is_approved=True) | Q(member=user))
            else:
                queryset = queryset.filter(is_approved=True)

            # 필터링: 고용형태
            employment_type = self.request.query_params.get('employment_type')
            if employment_type:
                queryset = queryset.filter(employment_type=employment_type)

            # 필터링: 직종 (JSONField occupations)
            occupation = self.request.query_params.get('occupation')
            if occupation:
                queryset = queryset.filter(occupations__contains=occupation)

            # 정렬: 프리미엄 우선 -> 최신순
            queryset = queryset.order_by('-is_premium', '-created_at')

        return queryset

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return success_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return success_response(JobNoticeSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response(serializer.data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success_response(JobNoticeSerializer(instance).data)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def premium_list(self, request):
        """
        GET /api/v1/recruit/notices/premium_list/ — 유효한 프리미엄 공고만 조회
        """
        today = timezone.now().date()
        queryset = self.get_queryset().filter(
            is_approved=True,
            is_premium=True,
            premium_start_date__lte=today,
            premium_end_date__gte=today,
        ).order_by('-premium_start_date')

        serializer = self.get_serializer(queryset, many=True)
        return success_response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsOwner])
    def premium(self, request, pk=None):
        """
        POST /api/v1/recruit/notices/:id/premium/ — 프리미엄 신청
        """
        days = int(request.data.get('days', 30))
        cost = int(request.data.get('cost', 10000))  # 기본 1만 포인트
        
        success, result = RecruitService.apply_premium(pk, request.user, days, cost)
        
        if success:
            return success_response({
                'message': f'프리미엄 신청이 완료되었습니다. ({days}일)',
                'premium_end_date': result.premium_end_date
            })
        else:
            return error_response('PAY_001', result, status=status.HTTP_400_BAD_REQUEST)


class JobSeekerViewSet(viewsets.ModelViewSet):
    """
    구직자 프로필 관리 ViewSet (본인 프로필만 조회/수정)
    """
    serializer_class = JobSeekerSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return JobSeeker.objects.filter(member=self.request.user, is_deleted=False)

    def perform_create(self, serializer):
        # 이미 프로필이 있으면 에러 처리하거나 업데이트로 유도 (여기서는 기존 것 있으면 에러)
        if JobSeeker.objects.filter(member=self.request.user, is_deleted=False).exists():
            raise RecruitService.ProfileAlreadyExistsException("이미 구직자 프로필이 존재합니다.")
        serializer.save(member=self.request.user, resume_registered=True)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return success_response(serializer.data)

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return success_response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return error_response('RECRUIT_001', str(e), status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response(serializer.data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success_response(serializer.data)
