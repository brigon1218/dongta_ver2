from django.urls import path
from . import views

urlpatterns = [
    # Phase 2.1: 모니터링 API
    path('status/', views.SystemStatusView.as_view(), name='monitoring-status'),
    path('routing/', views.RoutingStatsView.as_view(), name='monitoring-routing'),
    path('bridge/', views.BridgeAuthStatsView.as_view(), name='monitoring-bridge'),
    path('events/', views.EventStatusView.as_view(), name='monitoring-events'),
]
