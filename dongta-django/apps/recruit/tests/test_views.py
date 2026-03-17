import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.recruit.models import Company, JobNotice, JobSeeker
from apps.accounts.models import Member


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def member(db):
    return Member.objects.create_user(
        username='recruituser',
        email='recruit@example.com',
        name='채용유저',
        password='RecruitPass!1',
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
def company(db, member):
    return Company.objects.create(
        member=member,
        company_name='테스트회사',
        address='서울시 서초구',
    )


@pytest.fixture
def job_notice(db, member, company):
    return JobNotice.objects.create(
        member=member,
        company=company,
        employment_type='정규직',
        title='백엔드 개발자 채용',
        occupations=['개발'],
        is_approved=True,
    )


@pytest.mark.django_db
class TestCompanyViewSet:
    def test_list_requires_auth(self, api_client):
        url = reverse('company-list')
        response = api_client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_list_authenticated(self, auth_client):
        url = reverse('company-list')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_create_company(self, auth_client):
        url = reverse('company-list')
        data = {
            'company_name': '새회사',
            'phone': '02-111-2222',
            'address': '서울시 강남구',
        }
        response = auth_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_retrieve_company(self, auth_client, company):
        url = reverse('company-detail', kwargs={'pk': company.pk})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_update_company(self, auth_client, company):
        url = reverse('company-detail', kwargs={'pk': company.pk})
        data = {'company_name': '수정된회사'}
        response = auth_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestJobNoticeViewSet:
    def test_list_anonymous(self, api_client, job_notice):
        url = reverse('job-notice-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_list_filter_employment_type(self, api_client, job_notice):
        url = reverse('job-notice-list')
        response = api_client.get(url, {'employment_type': '정규직'})
        assert response.status_code == status.HTTP_200_OK

    def test_create_notice(self, auth_client, company):
        url = reverse('job-notice-list')
        data = {
            'company': company.pk,
            'employment_type': '계약직',
            'title': '프론트엔드 개발자',
            'occupations': ['웹개발'],
            'career_required': False,
            'payment_code': '',
        }
        response = auth_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_retrieve_notice(self, api_client, job_notice):
        url = reverse('job-notice-detail', kwargs={'pk': job_notice.pk})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_premium_list(self, api_client):
        url = reverse('job-notice-premium-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_update_notice_by_owner(self, auth_client, job_notice):
        url = reverse('job-notice-detail', kwargs={'pk': job_notice.pk})
        data = {'title': '수정된 공고 제목'}
        response = auth_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_update_notice_by_non_owner(self, api_client, other_member, job_notice):
        refresh = RefreshToken.for_user(other_member)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        url = reverse('job-notice-detail', kwargs={'pk': job_notice.pk})
        data = {'title': '다른유저가 수정'}
        response = api_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestJobSeekerViewSet:
    def test_list_requires_auth(self, api_client):
        url = reverse('job-seeker-list')
        response = api_client.get(url)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_list_authenticated(self, auth_client):
        url = reverse('job-seeker-list')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_create_job_seeker(self, auth_client):
        url = reverse('job-seeker-list')
        data = {
            'name': '홍길동',
            'gender': '남',
            'phone': '010-1111-2222',
            'email': 'hong@example.com',
            'address': '서울시',
        }
        response = auth_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
