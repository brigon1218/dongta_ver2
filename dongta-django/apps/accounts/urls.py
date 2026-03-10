from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='auth-register'),
    path('login/', views.LoginView.as_view(), name='auth-login'),
    path('logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='auth-token-refresh'),
    path('me/', views.MeView.as_view(), name='auth-me'),
    path('password/change/', views.PasswordChangeView.as_view(), name='auth-password-change'),
    path('password/reset/', views.PasswordResetRequestView.as_view(), name='auth-password-reset'),
    path('password/reset/confirm/', views.PasswordResetConfirmView.as_view(), name='auth-password-reset-confirm'),
    path('social/login/', views.SocialLoginView.as_view(), name='auth-social-login'),
]
