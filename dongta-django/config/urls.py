from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.core.views import LandingPageView

urlpatterns = [
    path('', LandingPageView.as_view(), name='landing'),

    path('admin/', admin.site.urls),

    # API v1
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/business/', include('apps.business114.urls')),
    path('api/v1/recruit/', include('apps.recruit.urls')),
    path('api/v1/payment/', include('apps.payment.urls')),
    path('api/v1/board/', include('apps.board.urls')),
    path('api/v1/mypage/', include('apps.mypage.urls')),
    path('api/v1/sync/', include('apps.sync.urls')),

    # API 문서
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
