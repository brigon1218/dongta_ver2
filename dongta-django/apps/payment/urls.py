from django.urls import path
from . import views

urlpatterns = [
    path('balance/', views.BalanceView.as_view(), name='payment-balance'),
    path('history/', views.PaymentHistoryListView.as_view(), name='payment-history'),
    path('charge/', views.PointChargeView.as_view(), name='payment-charge'),
    path('danal/ready/', views.DanalReadyView.as_view(), name='payment-danal-ready'),
    path('danal/callback/', views.DanalCallbackView.as_view(), name='payment-danal-callback'),
    path('danal/cancel/', views.DanalCancelView.as_view(), name='payment-danal-cancel'),
    path('use/', views.PointUseView.as_view(), name='payment-use'),
]
