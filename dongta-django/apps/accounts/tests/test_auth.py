import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from apps.accounts.models import Member, PasswordResetToken


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def member(db):
    return Member.objects.create_user(
        username='testuser',
        email='test@example.com',
        name='테스트유저',
        password='TestPass!1',
    )


@pytest.mark.django_db
class TestRegister:
    def test_register_success(self, api_client):
        url = reverse('auth-register')
        data = {
            'username': 'newuser',
            'password': 'NewPass!1',
            'password_confirm': 'NewPass!1',
            'name': '홍길동',
            'email': 'hong@example.com',
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True
        assert response.data['data']['username'] == 'newuser'

    def test_register_duplicate_username(self, api_client, member):
        url = reverse('auth-register')
        data = {
            'username': 'testuser',
            'password': 'NewPass!1',
            'password_confirm': 'NewPass!1',
            'name': '다른유저',
            'email': 'other@example.com',
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False

    def test_register_password_mismatch(self, api_client):
        url = reverse('auth-register')
        data = {
            'username': 'newuser2',
            'password': 'NewPass!1',
            'password_confirm': 'DifferentPass!1',
            'name': '홍길동',
            'email': 'hong2@example.com',
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, api_client, member):
        url = reverse('auth-login')
        response = api_client.post(url, {'username': 'testuser', 'password': 'TestPass!1'})
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data['data']
        assert 'refresh' in response.data['data']

    def test_login_wrong_password(self, api_client, member):
        url = reverse('auth-login')
        response = api_client.post(url, {'username': 'testuser', 'password': 'WrongPass'})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data['error']['code'] == 'AUTH_002'

    def test_login_nonexistent_user(self, api_client):
        url = reverse('auth-login')
        response = api_client.post(url, {'username': 'nobody', 'password': 'Pass!1'})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMe:
    def test_get_me_authenticated(self, api_client, member):
        api_client.force_authenticate(user=member)
        url = reverse('auth-me')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['username'] == 'testuser'

    def test_get_me_unauthenticated(self, api_client):
        url = reverse('auth-me')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPasswordReset:
    def test_password_reset_request_success(self, api_client, member):
        url = reverse('auth-password-reset')
        response = api_client.post(url, {'email': 'test@example.com'})
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        # 토큰이 생성되었는지 확인
        assert PasswordResetToken.objects.filter(member=member).exists()

    def test_password_reset_request_invalid_email(self, api_client):
        url = reverse('auth-password-reset')
        response = api_client.post(url, {'email': 'nonexistent@example.com'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_reset_confirm_success(self, api_client, member):
        # 재설정 토큰 생성
        reset_token = PasswordResetToken.create_token(member)

        url = reverse('auth-password-reset-confirm')
        data = {
            'token': reset_token.token,
            'new_password': 'NewPass!1',
            'new_password_confirm': 'NewPass!1',
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True

        # 토큰이 사용됨으로 표시되었는지 확인
        reset_token.refresh_from_db()
        assert reset_token.is_used is True

        # 새 비밀번호로 로그인 확인
        login_response = api_client.post(
            reverse('auth-login'),
            {'username': 'testuser', 'password': 'NewPass!1'}
        )
        assert login_response.status_code == status.HTTP_200_OK

    def test_password_reset_confirm_invalid_token(self, api_client):
        url = reverse('auth-password-reset-confirm')
        data = {
            'token': 'invalid_token',
            'new_password': 'NewPass!1',
            'new_password_confirm': 'NewPass!1',
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_reset_confirm_expired_token(self, api_client, member):
        # 만료된 토큰 생성
        from datetime import timedelta
        reset_token = PasswordResetToken.objects.create(
            member=member,
            token='expired_token_123',
            expires_at=timezone.now() - timedelta(hours=2),
        )

        url = reverse('auth-password-reset-confirm')
        data = {
            'token': reset_token.token,
            'new_password': 'NewPass!1',
            'new_password_confirm': 'NewPass!1',
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestSocialLogin:
    def test_social_login_invalid_provider(self, api_client):
        url = reverse('auth-social-login')
        data = {
            'provider': 'facebook',
            'access_token': 'test_token',
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_social_login_google_invalid_token(self, api_client):
        url = reverse('auth-social-login')
        data = {
            'provider': 'google',
            'access_token': 'invalid_token',
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_social_login_naver_invalid_token(self, api_client):
        url = reverse('auth-social-login')
        data = {
            'provider': 'naver',
            'access_token': 'invalid_token',
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
