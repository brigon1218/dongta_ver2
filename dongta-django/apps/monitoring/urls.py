from django.urls import path
from . import views

urlpatterns = [
    # Phase 2.1: 모니터링 API
    path('status/', views.SystemStatusView.as_view(), name='monitoring-status'),
    path('routing/', views.RoutingStatsView.as_view(), name='monitoring-routing'),
    path('bridge/', views.BridgeAuthStatsView.as_view(), name='monitoring-bridge'),
    # Design S7.4: /monitoring/auth/ (BridgeAuthStatsView alias)
    path('auth/', views.BridgeAuthStatsView.as_view(), name='monitoring-auth'),
    path('events/', views.EventStatusView.as_view(), name='monitoring-events'),
    # Design S7.3: Event retry endpoint in monitoring app
    path('events/<int:event_id>/retry/', views.EventRetryView.as_view(), name='monitoring-event-retry'),
]
