from django.urls import path
from .admin_views import (
    AdminNoticeApproveView,
    AdminBusinessApproveView,
    AdminMemberListView,
    AdminPaymentConfirmView,
)

urlpatterns = [
    path('notices/<int:pk>/approve/', AdminNoticeApproveView.as_view(), name='admin-notice-approve'),
    path('business/<int:pk>/approve/', AdminBusinessApproveView.as_view(), name='admin-business-approve'),
    path('members/', AdminMemberListView.as_view(), name='admin-member-list'),
    path('payment/confirm/', AdminPaymentConfirmView.as_view(), name='admin-payment-confirm'),
]
