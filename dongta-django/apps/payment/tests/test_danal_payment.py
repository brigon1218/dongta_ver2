"""
다날 결제 통합 테스트
- DanalClient 기본 기능
- Payment API Views (Ready, Callback, Cancel)
- MySQL 비동기 동기화
- 보안 검증 (HMAC, Rate Limiting)
"""
import hmac
import hashlib
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from apps.payment.models import PaymentHistory, PointAccount, PaymentStatus
from apps.payment.danal.client import DanalClient, DanalResponse

User = get_user_model()


class DanalClientTest(TestCase):
    """다날 SDK 클라이언트 단위 테스트"""

    def setUp(self):
        self.client = DanalClient()

    def test_danal_response_parsing(self):
        """DanalResponse가 다날 서버 응답을 올바르게 파싱하는지 확인"""
        raw_response = {
            'RETURNCODE': '0000',
            'RETURNMSG': 'success',
            'TID': 'test-tid-123',
            'STARTURL': 'https://example.com/payment'
        }
        response = DanalResponse(raw_response)

        self.assertTrue(response.is_success)
        self.assertEqual(response.return_code, '0000')
        self.assertEqual(response.return_msg, 'success')
        self.assertEqual(response.get('TID'), 'test-tid-123')
        self.assertEqual(response.get('STARTURL'), 'https://example.com/payment')

    def test_danal_response_error(self):
        """다날 에러 응답 처리"""
        raw_response = {
            'RETURNCODE': '0005',
            'RETURNMSG': 'Invalid CPID'
        }
        response = DanalResponse(raw_response)

        self.assertFalse(response.is_success)
        self.assertEqual(response.return_code, '0005')

    def test_danal_response_missing_field(self):
        """필수 필드가 없는 응답 처리"""
        response = DanalResponse({})
        self.assertFalse(response.is_success)
        self.assertIsNone(response.get('TID'))


@override_settings(
    DANAL_MERCHANT_ID='TEST_MERCHANT',
    DANAL_MERCHANT_KEY='test_secret_key',
    DANAL_CPID='TEST_CPID',
    DANAL_CPPWD='TEST_CPPWD',
    DANAL_RETURN_URL='http://localhost:8000/payment/callback/',
)
class PaymentReadyAPITest(APITestCase):
    """DanalReadyView API 테스트"""

    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client_api.force_authenticate(user=self.user)

    def test_danal_ready_success(self):
        """성공적인 다날 결제 준비 요청"""
        with patch('apps.payment.danal.client.DanalClient.ready') as mock_ready:
            mock_ready.return_value = DanalResponse({
                'RETURNCODE': '0000',
                'RETURNMSG': 'success',
                'TID': 'DANAL-20260307-001',
                'STARTURL': 'https://tx-creditcard.danal.co.kr/start?tid=DANAL-20260307-001'
            })

            response = self.client_api.post('/api/v1/payment/danal/ready/', {
                'amount': 10000,
                'pay_method': 'CARD'
            }, format='json')

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertIn('order_id', response.data['data'])
            self.assertIn('tid', response.data['data'])
            self.assertIn('start_url', response.data['data'])

            # 결제 내역 생성 확인
            payment = PaymentHistory.objects.filter(member=self.user).first()
            self.assertIsNotNone(payment)
            self.assertEqual(payment.amount, 10000)
            self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_danal_ready_failure(self):
        """다날 서버 오류 시 처리"""
        with patch('apps.payment.danal.client.DanalClient.ready') as mock_ready:
            mock_ready.return_value = DanalResponse({
                'RETURNCODE': '0005',
                'RETURNMSG': 'Invalid CPID'
            })

            response = self.client_api.post('/api/v1/payment/danal/ready/', {
                'amount': 10000,
                'pay_method': 'CARD'
            }, format='json')

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data['error_code'], 'PAY_002')

    def test_danal_ready_invalid_amount(self):
        """부정확한 금액 요청 (최소 1000원)"""
        response = self.client_api.post('/api/v1/payment/danal/ready/', {
            'amount': 100,  # 최소 1000원
            'pay_method': 'CARD'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_danal_ready_authentication_required(self):
        """인증되지 않은 사용자 요청 거절"""
        self.client_api.force_authenticate(user=None)
        response = self.client_api.post('/api/v1/payment/danal/ready/', {
            'amount': 10000,
            'pay_method': 'CARD'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(
    DANAL_MERCHANT_ID='TEST_MERCHANT',
    DANAL_MERCHANT_KEY='test_secret_key',
)
class PaymentCallbackAPITest(APITestCase):
    """DanalCallbackView API 테스트 (결제 승인)"""

    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.payment = PaymentHistory.objects.create(
            member=self.user,
            amount=10000,
            point_amount=10000,
            pay_method='CARD',
            status=PaymentStatus.PENDING,
            danal_order_id='DONGTA-TEST-001',
            tid='DANAL-20260307-001'
        )

    def _generate_hmac_signature(self, data: dict) -> str:
        """테스트용 HMAC 서명 생성"""
        verify_fields = [
            data.get('RETURNCODE', ''),
            data.get('RETURNMSG', ''),
            data.get('TID', ''),
            data.get('ORDERID', ''),
        ]
        verify_string = '|'.join(verify_fields)
        return hmac.new(
            'test_secret_key'.encode('utf-8'),
            verify_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def test_danal_callback_success(self):
        """성공적인 다날 결제 콜백 수신 및 승인"""
        with patch('apps.payment.danal.client.DanalClient.approve') as mock_approve:
            mock_approve.return_value = DanalResponse({
                'RETURNCODE': '0000',
                'RETURNMSG': 'success',
                'TID': 'DANAL-20260307-001',
            })

            # HMAC 서명 생성
            callback_data = {
                'RETURNCODE': '0000',
                'RETURNMSG': 'success',
                'TID': 'DANAL-20260307-001',
                'ORDERID': 'DONGTA-TEST-001',
            }
            hmac_sig = self._generate_hmac_signature(callback_data)
            callback_data['HMAC'] = hmac_sig

            response = self.client_api.post('/api/v1/payment/danal/callback/', callback_data, format='json')

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('message', response.data['data'])

            # 결제 내역 상태 확인
            self.payment.refresh_from_db()
            self.assertEqual(self.payment.status, PaymentStatus.APPROVED)
            self.assertTrue(self.payment.is_success)

            # 포인트 적립 확인
            point_account = PointAccount.objects.get(member=self.user)
            self.assertEqual(point_account.total_charged, 10000)

    def test_danal_callback_invalid_hmac(self):
        """잘못된 HMAC 서명으로 콜백 거절"""
        callback_data = {
            'RETURNCODE': '0000',
            'RETURNMSG': 'success',
            'TID': 'DANAL-20260307-001',
            'ORDERID': 'DONGTA-TEST-001',
            'HMAC': 'invalid_hmac_signature'
        }

        response = self.client_api.post('/api/v1/payment/danal/callback/', callback_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error_code'], 'PAY_005')

    def test_danal_callback_missing_tid(self):
        """TID 없는 콜백 요청 거절"""
        response = self.client_api.post('/api/v1/payment/danal/callback/', {
            'ORDERID': 'DONGTA-TEST-001',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error_code'], 'PAY_003')

    def test_danal_callback_duplicate_approval(self):
        """이미 승인된 결제의 중복 승인 처리"""
        # 첫 번째 승인
        self.payment.status = PaymentStatus.APPROVED
        self.payment.is_success = True
        self.payment.save()

        callback_data = {
            'RETURNCODE': '0000',
            'RETURNMSG': 'success',
            'TID': 'DANAL-20260307-001',
            'ORDERID': 'DONGTA-TEST-001',
        }
        hmac_sig = self._generate_hmac_signature(callback_data)
        callback_data['HMAC'] = hmac_sig

        response = self.client_api.post('/api/v1/payment/danal/callback/', callback_data, format='json')

        # 이미 승인된 결제는 재승인하지 않도록 처리
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('이미 승인된 결제입니다', response.data['data']['message'])

    def test_danal_callback_nonexistent_order(self):
        """존재하지 않는 주문의 콜백 거절"""
        callback_data = {
            'RETURNCODE': '0000',
            'RETURNMSG': 'success',
            'TID': 'DANAL-FAKE-999',
            'ORDERID': 'DONGTA-NONEXISTENT',
        }
        hmac_sig = self._generate_hmac_signature(callback_data)
        callback_data['HMAC'] = hmac_sig

        response = self.client_api.post('/api/v1/payment/danal/callback/', callback_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error_code'], 'PAY_002')


class PaymentCancelAPITest(APITestCase):
    """DanalCancelView API 테스트"""

    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client_api.force_authenticate(user=self.user)

        # 포인트 계정 및 결제 내역 생성
        self.point_account = PointAccount.objects.create(
            member=self.user,
            total_charged=10000,
            total_used=0
        )
        self.payment = PaymentHistory.objects.create(
            member=self.user,
            amount=10000,
            point_amount=10000,
            pay_method='CARD',
            status=PaymentStatus.APPROVED,
            is_success=True,
            danal_order_id='DONGTA-TEST-001',
            tid='DANAL-20260307-001'
        )

    def test_danal_cancel_success(self):
        """성공적인 다날 결제 취소"""
        with patch('apps.payment.danal.client.DanalClient.cancel') as mock_cancel:
            mock_cancel.return_value = DanalResponse({
                'RETURNCODE': '0000',
                'RETURNMSG': 'success',
                'TID': 'DANAL-20260307-001',
            })

            response = self.client_api.post('/api/v1/payment/danal/cancel/', {
                'payment_id': self.payment.id,
                'reason': '사용자 요청 취소'
            }, format='json')

            self.assertEqual(response.status_code, status.HTTP_200_OK)

            # 결제 상태 확인
            self.payment.refresh_from_db()
            self.assertEqual(self.payment.status, PaymentStatus.CANCELLED)

    def test_danal_cancel_nonexistent_payment(self):
        """존재하지 않는 결제 취소 요청"""
        response = self.client_api.post('/api/v1/payment/danal/cancel/', {
            'payment_id': 9999,
            'reason': '사용자 요청 취소'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error_code'], 'PAY_002')

    def test_danal_cancel_unapproved_payment(self):
        """승인되지 않은 결제 취소 요청"""
        unapproved_payment = PaymentHistory.objects.create(
            member=self.user,
            amount=5000,
            point_amount=5000,
            pay_method='CARD',
            status=PaymentStatus.PENDING,
            danal_order_id='DONGTA-TEST-002',
            tid='DANAL-20260307-002'
        )

        response = self.client_api.post('/api/v1/payment/danal/cancel/', {
            'payment_id': unapproved_payment.id,
            'reason': '사용자 요청 취소'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error_code'], 'PAY_002')


class PointOperationAPITest(APITestCase):
    """포인트 조회, 충전, 사용 API 테스트"""

    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client_api.force_authenticate(user=self.user)
        self.point_account = PointAccount.objects.create(
            member=self.user,
            total_charged=50000,
            total_used=10000
        )

    def test_balance_view(self):
        """포인트 잔액 조회"""
        response = self.client_api.get('/api/v1/payment/balance/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['total_charged'], 50000)
        self.assertEqual(response.data['data']['total_used'], 10000)
        self.assertEqual(response.data['data']['balance'], 40000)  # 잔액 = 충전액 - 사용액

    def test_point_use_success(self):
        """포인트 차감 성공"""
        response = self.client_api.post('/api/v1/payment/use/', {
            'amount': 5000
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.point_account.refresh_from_db()
        self.assertEqual(self.point_account.total_used, 15000)

    def test_point_use_insufficient_balance(self):
        """포인트 부족 시 거절"""
        response = self.client_api.post('/api/v1/payment/use/', {
            'amount': 50000  # 잔액 40000보다 많음
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error_code'], 'PAY_001')

    def test_point_charge_request(self):
        """포인트 충전 요청"""
        response = self.client_api.post('/api/v1/payment/charge/', {
            'amount': 10000,
            'pay_method': 'CARD'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('order_id', response.data['data'])
        self.assertIn('payment_id', response.data['data'])


class PaymentHistoryAPITest(APITestCase):
    """결제 내역 조회 API 테스트"""

    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client_api.force_authenticate(user=self.user)

        # 여러 결제 내역 생성
        for i in range(5):
            PaymentHistory.objects.create(
                member=self.user,
                amount=10000,
                point_amount=10000,
                pay_method='CARD',
                status=PaymentStatus.APPROVED if i % 2 == 0 else PaymentStatus.REJECTED,
                is_success=i % 2 == 0,
                danal_order_id=f'DONGTA-TEST-{i:03d}',
                tid=f'DANAL-{i:03d}'
            )

    def test_payment_history_list(self):
        """전체 결제 내역 조회"""
        response = self.client_api.get('/api/v1/payment/history/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 5)

    def test_payment_history_filter_success(self):
        """성공한 결제만 조회"""
        response = self.client_api.get('/api/v1/payment/history/?is_success=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 3)  # 5개 중 3개가 성공 (i % 2 == 0)

    def test_payment_history_pagination(self):
        """결제 내역 페이지네이션"""
        response = self.client_api.get('/api/v1/payment/history/?page=1&limit=2')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 2)
        self.assertEqual(response.data['meta']['total'], 5)
