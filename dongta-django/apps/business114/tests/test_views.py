import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.business114.models import Business, BusinessType
from apps.accounts.models import Member


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def member(db):
    return Member.objects.create_user(
        username='bizuser',
        email='biz@example.com',
        name='업체유저',
        password='BizPass!1',
    )


@pytest.fixture
def other_member(db):
    return Member.objects.create_user(
        username='otheruser',
        email='other@example.com',
        name='다른유저',
        password='OtherPass!1',
    )


@pytest.fixture
def auth_client(api_client, member):
    refresh = RefreshToken.for_user(member)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def business(db, member):
    return Business.objects.create(
        member=member,
        business_type=BusinessType.STORE,
        corp_name='테스트업체',
        phone='02-1234-5678',
        address='서울시 강남구',
        industry_type=1,
        items=[1, 2],
        is_approved=True,
    )


@pytest.mark.django_db
class TestBusinessListView:
    def test_list_unauthenticated(self, api_client, business):
        url = reverse('business-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_approved_only_for_anonymous(self, api_client, member):
        approved = Business.objects.create(
            member=member, business_type=BusinessType.STORE,
            corp_name='승인업체', address='서울', industry_type=1, is_approved=True
        )
        unapproved = Business.objects.create(
            member=member, business_type=BusinessType.STORE,
            corp_name='미승인업체', address='서울', industry_type=1, is_approved=False
        )
        url = reverse('business-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        corp_names = [item['corp_name'] for item in response.data.get('data', response.data.get('results', []))]
        assert '승인업체' in corp_names
        assert '미승인업체' not in corp_names

    def test_list_search_by_q(self, api_client, business):
        url = reverse('business-list')
        response = api_client.get(url, {'q': '테스트업체'})
        assert response.status_code == status.HTTP_200_OK

    def test_list_filter_by_industry_type(self, api_client, business):
        url = reverse('business-list')
        response = api_client.get(url, {'industry_type': 1})
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestBusinessRetrieveView:
    def test_retrieve_increments_view_count(self, api_client, business):
        initial_count = business.view_count
        url = reverse('business-detail', kwargs={'pk': business.pk})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        business.refresh_from_db()
        assert business.view_count == initial_count + 1


@pytest.mark.django_db
class TestBusinessCreateView:
    def test_create_requires_auth(self, api_client):
        url = reverse('business-list')
        data = {
            'business_type': BusinessType.STORE,
            'corp_name': '새업체',
            'address': '서울시 마포구',
            'industry_type': 2,
            'items': [],
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_create_success(self, auth_client):
        url = reverse('business-list')
        data = {
            'business_type': BusinessType.STORE,
            'corp_name': '새업체',
            'address': '서울시 마포구',
            'industry_type': 2,
            'items': [1, 2],
        }
        response = auth_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_sets_unapproved(self, auth_client):
        url = reverse('business-list')
        data = {
            'business_type': BusinessType.FACTORY,
            'corp_name': '신규공장',
            'address': '경기도 안산시',
            'industry_type': 3,
            'items': [],
        }
        response = auth_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['data']['is_approved'] is False


@pytest.mark.django_db
class TestBusinessUpdateView:
    def test_update_by_owner(self, auth_client, business):
        url = reverse('business-detail', kwargs={'pk': business.pk})
        data = {'corp_name': '수정된업체명'}
        response = auth_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_update_by_non_owner(self, api_client, other_member, business):
        refresh = RefreshToken.for_user(other_member)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        url = reverse('business-detail', kwargs={'pk': business.pk})
        data = {'corp_name': '다른유저가수정'}
        response = api_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestBusinessMyView:
    def test_my_businesses(self, auth_client, business):
        url = reverse('business-my')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_my_businesses_requires_auth(self, api_client):
        url = reverse('business-my')
        response = api_client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
