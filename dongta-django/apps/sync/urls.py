"""
apps/sync/urls.py

동기화 모니터링 API URL 설정 (관리자 전용).
"""
from django.urls import path

from . import views

app_name = 'sync'

urlpatterns = [
    path('status/', views.SyncStatusView.as_view(), name='sync-status'),
    path('events/', views.EventOutboxListView.as_view(), name='event-outbox-list'),
    path('events/<int:pk>/retry/', views.EventOutboxRetryView.as_view(), name='event-outbox-retry'),
    path('logs/', views.SyncLogListView.as_view(), name='sync-log-list'),
]
