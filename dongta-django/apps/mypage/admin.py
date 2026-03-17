from django.contrib import admin
from .models import MyFolder, MyData


@admin.register(MyFolder)
class MyFolderAdmin(admin.ModelAdmin):
    list_display = ['id', 'member', 'name', 'created_at', 'is_deleted']
    search_fields = ['member__username', 'name']
    list_filter = ['is_deleted']


@admin.register(MyData)
class MyDataAdmin(admin.ModelAdmin):
    list_display = ['id', 'member', 'folder', 'content_type', 'object_id', 'created_at']
    search_fields = ['member__username', 'folder__name']
    list_filter = ['content_type', 'is_deleted']
