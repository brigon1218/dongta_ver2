from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.ProfileView.as_view(), name='mypage-profile'),
    path('password/', views.PasswordChangeView.as_view(), name='mypage-password'),
    path('withdraw/', views.WithdrawalView.as_view(), name='mypage-withdraw'),
    path('points/', views.PointHistoryView.as_view(), name='mypage-points'),
    path('summary/', views.ActivitySummaryView.as_view(), name='mypage-summary'),
]
