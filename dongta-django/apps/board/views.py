from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import F
from core.utils import success_response, error_response
from core.permissions import IsOwnerOrReadOnly
from .models import Post, Comment, PostLike, PostCategory
from .serializers import (
    PostListSerializer,
    PostDetailSerializer,
    PostCreateSerializer,
    CommentSerializer
)
from .permissions import PostPermission


class PostViewSet(viewsets.ModelViewSet):
    """
    게시글 관리 ViewSet
    """
    permission_classes = [PostPermission]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PostCreateSerializer
        if self.action == 'retrieve':
            return PostDetailSerializer
        return PostListSerializer

    def get_queryset(self):
        queryset = Post.objects.filter(is_deleted=False).select_related('member')
        
        # 필터: 카테고리
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
            
        # 검색: q
        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(title__icontains=q) | queryset.filter(content__icontains=q)
            
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

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # 조회수 증가
        Post.objects.filter(pk=instance.pk).update(view_count=F('view_count') + 1)
        instance.refresh_from_db(fields=['view_count'])
        serializer = self.get_serializer(instance)
        return success_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return success_response(
            PostDetailSerializer(serializer.instance, context={'request': request}).data, 
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success_response(PostDetailSerializer(instance, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def like(self, request, pk=None):
        """
        POST /api/v1/board/posts/:id/like/ — 추천 토글
        """
        post = self.get_object()
        user = request.user
        
        with transaction.atomic():
            like_exists = PostLike.objects.filter(post=post, member=user).exists()
            
            if like_exists:
                # 추천 취소
                PostLike.objects.filter(post=post, member=user).delete()
                Post.objects.filter(pk=post.pk).update(like_count=F('like_count') - 1)
                message = "추천을 취소했습니다."
                liked = False
            else:
                # 추천 등록
                PostLike.objects.create(post=post, member=user)
                Post.objects.filter(pk=post.pk).update(like_count=F('like_count') + 1)
                message = "이 글을 추천했습니다."
                liked = True
                
        post.refresh_from_db(fields=['like_count'])
        return success_response({
            'message': message,
            'liked': liked,
            'like_count': post.like_count
        })


class CommentViewSet(viewsets.ModelViewSet):
    """
    댓글 관리 ViewSet
    """
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        # 특정 게시글의 댓글만 모아보기 등은 PostViewSet의 retrieve 내에서 처리하므로
        # 여기서는 개별 댓글 조작(삭제 등) 위주로 구성
        return Comment.objects.filter(is_deleted=False)

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return success_response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return success_response({'message': '댓글이 삭제되었습니다.'})
