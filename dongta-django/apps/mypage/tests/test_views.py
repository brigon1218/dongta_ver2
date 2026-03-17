import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.models import Member
from apps.payment.models import PointAccount


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def member(db):
    return Member.objects.create_user(
        username='mypageuser',
        email='mypage@example.com',
        name='마이페이지유저',
        password='MypagePass!1',
    )


@pytest.fixture
def auth_client(api_client, member):
    refresh = RefreshToken.for_user(member)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.mark.django_db
class TestProfileView:
    def test_get_profile_requires_auth(self, api_client):
        url = reverse('mypage-profile')
        response = api_client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_get_profile_authenticated(self, auth_client, member):
        url = reverse('mypage-profile')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['username'] == 'mypageuser'

    def test_update_profile(self, auth_client):
        url = reverse('mypage-profile')
        data = {'name': '수정된이름', 'email': 'updated@example.com'}
        response = auth_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['name'] == '수정된이름'


@pytest.mark.django_db
class TestPasswordChangeView:
    def test_change_password_success(self, auth_client):
        url = reverse('mypage-password')
        data = {
            'old_password': 'MypagePass!1',
            'new_password': 'NewMypagePass!2',
        }
        response = auth_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True

    def test_change_password_wrong_old(self, auth_client):
        url = reverse('mypage-password')
        data = {
            'old_password': 'WrongPass!1',
            'new_password': 'NewMypagePass!2',
        }
        response = auth_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False

    def test_change_password_requires_auth(self, api_client):
        url = reverse('mypage-password')
        response = api_client.post(url, {})
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


@pytest.mark.django_db
class TestPointHistoryView:
    def test_get_points_requires_auth(self, api_client):
        url = reverse('mypage-points')
        response = api_client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_get_points_authenticated(self, auth_client, member):
        PointAccount.objects.create(member=member, total_charged=10000, total_used=3000)
        url = reverse('mypage-points')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestActivitySummaryView:
    def test_summary_requires_auth(self, api_client):
        url = reverse('mypage-summary')
        response = api_client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_summary_authenticated(self, auth_client):
        url = reverse('mypage-summary')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert 'posts_count' in data
        assert 'comments_count' in data
        assert 'businesses_count' in data
        assert 'job_notices_count' in data
