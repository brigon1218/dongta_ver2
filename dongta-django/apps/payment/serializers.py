from rest_framework import serializers
from .models import PointAccount, PaymentHistory


class PointAccountSerializer(serializers.ModelSerializer):
    """포인트 계정 시리얼라이저"""
    balance = serializers.IntegerField(read_only=True)

    class Meta:
        model = PointAccount
        fields = [
            'total_charged', 'total_used', 'balance',
            'last_charged_at', 'last_used_at',
        ]
        read_only_fields = [
            'total_charged', 'total_used', 'balance',
            'last_charged_at', 'last_used_at',
        ]


class PaymentHistorySerializer(serializers.ModelSerializer):
    """결제 내역 시리얼라이저"""
    pay_method_display = serializers.CharField(
        source='get_pay_method_display', read_only=True
    )

    class Meta:
        model = PaymentHistory
        fields = [
            'id', 'amount', 'point_amount',
            'pay_method', 'pay_method_display',
            'is_success', 'result_code', 'result_message',
            'danal_order_id', 'confirmed_at', 'created_at',
        ]
        read_only_fields = (
            'id', 'amount', 'point_amount',
            'pay_method_display',
            'is_success', 'result_code', 'result_message',
            'danal_order_id', 'confirmed_at', 'created_at',
        )


class PointUseSerializer(serializers.Serializer):
    """포인트 차감 요청 시리얼라이저"""
    amount = serializers.IntegerField(min_value=1)
    description = serializers.CharField(max_length=200, required=False, default='서비스 사용')


class PointChargeSerializer(serializers.Serializer):
    """포인트 충전 요청 시리얼라이저"""
    amount = serializers.IntegerField(min_value=1000, help_text='충전 금액 (원, 최소 1000원)')
    pay_method = serializers.ChoiceField(choices=PaymentHistory.PayMethod.choices)


class DanalReadySerializer(serializers.Serializer):
    """다날 결제 준비 요청 시리얼라이저"""
    amount = serializers.IntegerField(min_value=1000, help_text='결제 금액 (원)')
    pay_method = serializers.ChoiceField(
        choices=PaymentHistory.PayMethod.choices,
        default=PaymentHistory.PayMethod.CARD
    )


class DanalCallbackSerializer(serializers.Serializer):
    """다날 결제 콜백 수신 시리얼라이저 (서버-서버)"""
    order_id = serializers.CharField(max_length=100)
    result_code = serializers.CharField(max_length=50)
    result_message = serializers.CharField(max_length=200, required=False, default='')
    amount = serializers.IntegerField(required=False, default=0)
