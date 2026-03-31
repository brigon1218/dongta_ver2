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
