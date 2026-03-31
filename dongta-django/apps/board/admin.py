from django.contrib import admin
from .models import Post, Comment, PostLike


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'category', 'title', 'member',
        'view_count', 'like_count', 'is_pinned', 'created_at'
    ]
    list_filter = ['category', 'is_pinned', 'created_at']
    search_fields = ['title', 'content', 'member__username']
    raw_id_fields = ['member']
    actions = ['delete_posts']

    @admin.action(description='선택된 게시글 삭제')
    def delete_posts(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'{count}개의 게시글이 삭제되었습니다.')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'post', 'member', 'parent', 'created_at']
    list_filter = ['created_at']
    search_fields = ['content', 'member__username']
    raw_id_fields = ['post', 'member', 'parent']


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ['post', 'member', 'created_at']
    raw_id_fields = ['post', 'member']
