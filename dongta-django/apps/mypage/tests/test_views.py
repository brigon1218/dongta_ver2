"""
마이페이지(mypage) 뷰 통합 테스트

테스트 대상:
- ProfileView (GET/PATCH /api/v1/mypage/profile/)
- PasswordChangeView (POST /api/v1/mypage/password/)
- WithdrawalView (POST /api/v1/mypage/withdraw/)
- PointHistoryView (GET /api/v1/mypage/points/)
- ActivitySummaryView (GET /api/v1/mypage/summary/)
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import Member
from apps.payment.models import PaymentHistory, PointAccount, PaymentStatus
from apps.board.models import Post, PostCategory
from apps.business114.models import Business, BusinessType
from apps.recruit.models import JobNotice


class MypageTestBase(TestCase):
    """마이페이지 테스트 공통 기반 클래스"""

    def setUp(self):
        self.client = APIClient()
        self.user = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!',
            name='테스트유저',
        )
        self.client.force_authenticate(user=self.user)

    def get_url(self, name):
        return reverse(name)


class ProfileViewTest(MypageTestBase):
    """ProfileView 테스트 — GET/PATCH /api/v1/mypage/profile/"""

    def test_profile_retrieve(self):
        """프로필 조회: 인증된 사용자는 자신의 프로필을 조회할 수 있다."""
        url = self.get_url('mypage-profile')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['data']['username'], self.user.username)
        self.assertEqual(data['data']['email'], self.user.email)

    def test_profile_update_partial(self):
        """프로필 수정(PATCH): partial update가 정상 동작한다."""
        url = self.get_url('mypage-profile')
        payload = {'phone': '010-1234-5678', 'region': '서울'}
        response = self.client.patch(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['data']['phone'], '010-1234-5678')
        self.assertEqual(data['data']['region'], '서울')

        # DB에도 실제 반영됐는지 확인
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, '010-1234-5678')


class PasswordChangeViewTest(MypageTestBase):
    """PasswordChangeView 테스트 — POST /api/v1/mypage/password/"""

    def test_password_change_success(self):
        """비밀번호 변경: 올바른 현재 비밀번호 입력 시 변경에 성공한다."""
        url = self.get_url('mypage-password')
        payload = {
            'old_password': 'TestPass123!',
            'new_password': 'NewPass456@',
        }
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 변경 후 새 비밀번호로 인증 가능한지 확인
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456@'))

    def test_password_change_fail_wrong_old_password(self):
        """비밀번호 변경 실패: 현재 비밀번호가 틀리면 400을 반환한다."""
        url = self.get_url('mypage-password')
        payload = {
            'old_password': 'WrongOldPass!',
            'new_password': 'NewPass456@',
        }
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertEqual(data['code'], 'AUTH_002')


class WithdrawalViewTest(MypageTestBase):
    """WithdrawalView 테스트 — POST /api/v1/mypage/withdraw/"""

    def test_withdrawal_soft_delete(self):
        """회원 탈퇴: soft delete, is_active=False, want_quit=True가 설정된다."""
        url = self.get_url('mypage-withdraw')
        payload = {'password': 'TestPass123!', 'reason': '서비스 불만족'}
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(self.user.want_quit)
        self.assertEqual(self.user.quit_reason, '서비스 불만족')
        # soft_delete() 호출로 is_deleted=True 설정 확인
        self.assertTrue(self.user.is_deleted)

    def test_withdrawal_fail_wrong_password(self):
        """회원 탈퇴 실패: 비밀번호가 틀리면 400을 반환하고 탈퇴되지 않는다."""
        url = self.get_url('mypage-withdraw')
        payload = {'password': 'WrongPassword!'}
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertEqual(data['code'], 'AUTH_002')

        # 탈퇴 처리가 되지 않았는지 확인
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertFalse(self.user.want_quit)


class PointHistoryViewTest(MypageTestBase):
    """PointHistoryView 테스트 — GET /api/v1/mypage/points/"""

    def test_points_list_with_balance(self):
        """포인트 내역 조회: balance와 history 필드를 포함해 반환한다."""
        # PointAccount 및 PaymentHistory 생성
        point_account = PointAccount.objects.create(
            member=self.user,
            total_charged=50000,
            total_used=10000,
        )
        PaymentHistory.objects.create(
            member=self.user,
            amount=50000,
            point_amount=50000,
            pay_method=PaymentHistory.PayMethod.CARD,
            status=PaymentStatus.APPROVED,
        )

        url = self.get_url('mypage-points')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('balance', data['data'])
        self.assertIn('history', data['data'])
        # 잔액 = 총충전(50000) - 총사용(10000) = 40000
        self.assertEqual(data['data']['balance'], 40000)
        self.assertEqual(len(data['data']['history']), 1)


class ActivitySummaryViewTest(MypageTestBase):
    """ActivitySummaryView 테스트 — GET /api/v1/mypage/summary/"""

    def test_activity_summary_count_accuracy(self):
        """활동 요약: 게시글/댓글/사업장/공고 카운트가 정확히 반영된다."""
        # 각 앱 데이터 생성
        Post.objects.create(member=self.user, title='테스트 게시글', content='내용', category=PostCategory.FREE)
        Post.objects.create(member=self.user, title='테스트 게시글2', content='내용2', category=PostCategory.FREE)
        Business.objects.create(
            member=self.user,
            corp_name='테스트 사업장',
            business_type=BusinessType.STORE,
            address='서울 강남구',
        )

        url = self.get_url('mypage-summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['data']['posts_count'], 2)
        self.assertEqual(data['data']['businesses_count'], 1)
        self.assertEqual(data['data']['comments_count'], 0)
        self.assertEqual(data['data']['job_notices_count'], 0)


class UnauthorizedAccessTest(TestCase):
    """비인증 사용자 접근 제한 테스트"""

    def setUp(self):
        self.client = APIClient()
        # 인증 없이 요청

    def test_unauthorized_access_returns_401(self):
        """비인증 사용자가 마이페이지 엔드포인트에 접근하면 401을 반환한다."""
        urls = [
            reverse('mypage-profile'),
            reverse('mypage-password'),
            reverse('mypage-withdraw'),
            reverse('mypage-points'),
            reverse('mypage-summary'),
        ]
        for url in urls:
            # GET 요청 시도
            response = self.client.get(url)
            self.assertIn(
                response.status_code,
                [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
                msg=f'{url} 접근 시 인증 오류를 반환해야 합니다.',
            )
