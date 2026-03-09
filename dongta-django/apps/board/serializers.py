from rest_framework import serializers
from .models import Post, Comment, PostCategory


class CommentSerializer(serializers.ModelSerializer):
    """
    댓글 시리얼라이저 (대댓글 포함)
    """
    member_username = serializers.CharField(source='member.username', read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'post', 'member', 'member_username', 
            'parent', 'content', 'replies', 'created_at'
        ]
        read_only_fields = ['id', 'member', 'created_at']

    def get_replies(self, obj):
        if obj.replies.exists():
            return CommentSerializer(obj.replies.all(), many=True).data
        return []


class PostListSerializer(serializers.ModelSerializer):
    """
    게시글 목록용 시리얼라이저 (경량)
    """
    member_username = serializers.CharField(source='member.username', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'category', 'category_display', 'title', 
            'member_username', 'view_count', 'like_count', 
            'is_pinned', 'created_at'
        ]


class PostDetailSerializer(serializers.ModelSerializer):
    """
    게시글 상세 시리얼라이저 (댓글 포함)
    """
    member_username = serializers.CharField(source='member.username', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    comments = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'category', 'category_display', 'title', 'content', 
            'member', 'member_username', 'view_count', 'like_count', 
            'is_pinned', 'is_liked', 'comments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'member', 'view_count', 'like_count', 'created_at', 'updated_at']

    def get_comments(self, obj):
        # 최상위 댓글만 가져오고, 그 아래 대댓글은 CommentSerializer 내에서 처리
        top_level_comments = obj.comments.filter(parent=None)
        return CommentSerializer(top_level_comments, many=True).data

    def get_is_liked(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            return obj.likes.filter(member=user).exists()
        return False


class PostCreateSerializer(serializers.ModelSerializer):
    """
    게시글 등록/수정용 시리얼라이저
    """
    class Meta:
        model = Post
        fields = ['category', 'title', 'content', 'is_pinned']

    def validate_is_pinned(self, value):
        # 일반 유저는 상단 고정 기능을 사용할 수 없도록 제한 (필요 시)
        user = self.context.get('request').user
        if value and not user.is_staff:
            raise serializers.ValidationError("상단 고정 권한이 없습니다.")
        return value
