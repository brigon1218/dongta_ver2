from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'companies', views.CompanyViewSet, basename='company')
router.register(r'notices', views.JobNoticeViewSet, basename='job-notice')
router.register(r'seekers', views.JobSeekerViewSet, basename='job-seeker')

urlpatterns = [
    path('', include(router.urls)),
]
