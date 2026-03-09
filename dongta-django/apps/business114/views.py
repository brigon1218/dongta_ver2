from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import Q, F
from core.utils import success_response, error_response
from core.permissions import IsOwnerOrReadOnly
from .models import Business
from .serializers import (
    BusinessListSerializer,
    BusinessDetailSerializer,
    BusinessCreateSerializer,
)


class BusinessViewSet(viewsets.ModelViewSet):
    """
    동타114 업체 관리 ViewSet
    """
    permission_classes = [IsOwnerOrReadOnly]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return BusinessCreateSerializer
        if self.action == 'retrieve':
            return BusinessDetailSerializer
        return BusinessListSerializer

    def get_queryset(self):
        queryset = Business.objects.filter(is_deleted=False)
        
        # 목록 조회 시에는 승인된 업체만 노출 (단, 본인 등록 업체는 미승인 상태도 노출)
        if self.action == 'list':
            user = self.request.user
            if user.is_authenticated:
                queryset = queryset.filter(Q(is_approved=True) | Q(member=user))
            else:
                queryset = queryset.filter(is_approved=True)

            # 검색: q (업체명, 키워드, 설명 통합)
            q = self.request.query_params.get('q')
            if q:
                queryset = queryset.filter(
                    Q(corp_name__icontains=q) |
                    Q(keywords__icontains=q) |
                    Q(description__icontains=q)
                )

            # 필터: 지역
            region = self.request.query_params.get('region')
            if region:
                queryset = queryset.filter(address__icontains=region)

            # 필터: 업종
            industry_type = self.request.query_params.get('industry_type')
            if industry_type:
                queryset = queryset.filter(industry_type=industry_type)

            # 필터: 품목 (JSONField items 내 특정 ID 포함 여부)
            item = self.request.query_params.get('item')
            if item:
                # JSONField 내에 해당 정수가 포함되어 있는지 확인
                # 문자열로 들어오는 경우를 대비해 처리
                try:
                    item_id = int(item)
                    queryset = queryset.filter(items__contains=item_id)
                except ValueError:
                    pass

            # 정렬
            sort = self.request.query_params.get('sort', 'newest')
            if sort == 'hits':
                queryset = queryset.order_by('-view_count', '-created_at')
            else:
                queryset = queryset.order_by('-created_at')

        return queryset

    def perform_create(self, serializer):
        # 신규 등록 시에는 본인을 소유자로 지정하고 승인 대기 상태로 저장
        serializer.save(member=self.request.user, is_approved=False)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return success_response(serializer.data)

    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return error_response('AUTH_001', '인증이 필요합니다.', status=status.HTTP_401_UNAUTHORIZED)
            
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return success_response(
            BusinessDetailSerializer(serializer.instance).data, 
            status=status.HTTP_201_CREATED
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # 조회수 증가 (F 객체 사용하여 Race Condition 방지)
        Business.objects.filter(pk=instance.pk).update(view_count=F('view_count') + 1)
        instance.refresh_from_db(fields=['view_count'])
        
        serializer = self.get_serializer(instance)
        return success_response(serializer.data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success_response(BusinessDetailSerializer(instance).data)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my(self, request):
        """
        GET /api/v1/business/my/ — 내가 등록한 업체 목록 조회
        """
        queryset = Business.objects.filter(member=request.user, is_deleted=False).order_by('-created_at')
        serializer = BusinessListSerializer(queryset, many=True)
        return success_response(serializer.data)
