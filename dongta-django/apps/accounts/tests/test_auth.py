import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.accounts.models import Member


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
