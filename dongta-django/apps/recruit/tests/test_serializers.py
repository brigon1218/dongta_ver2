import pytest
from apps.recruit.models import Company, JobNotice, JobSeeker
from apps.recruit.serializers import (
    CompanySerializer,
    JobNoticeSerializer,
    JobNoticeCreateSerializer,
    JobSeekerSerializer,
)
from apps.accounts.models import Member


@pytest.fixture
def member(db):
    return Member.objects.create_user(
        username='recruituser',
        email='recruit@example.com',
        name='채용유저',
        password='RecruitPass!1',
    )


@pytest.fixture
def company(db, member):
    return Company.objects.create(
        member=member,
        company_name='테스트회사',
        phone='02-9876-5432',
        address='서울시 서초구',
    )


@pytest.fixture
def job_notice(db, member, company):
    return JobNotice.objects.create(
        member=member,
        company=company,
        employment_type='정규직',
        title='백엔드 개발자 채용',
        occupations=['개발', 'IT'],
        career_required=True,
        is_approved=True,
    )


@pytest.fixture
def job_seeker(db, member):
    return JobSeeker.objects.create(
        member=member,
        name='홍길동',
        resume_registered=True,
    )


@pytest.mark.django_db
class TestCompanySerializer:
    def test_serializer_fields(self, company):
        serializer = CompanySerializer(company)
        data = serializer.data
        assert 'id' in data
        assert 'company_name' in data
        assert 'phone' in data
        assert 'address' in data
        assert 'has_notice' in data

    def test_serializer_values(self, company):
        serializer = CompanySerializer(company)
        data = serializer.data
        assert data['company_name'] == '테스트회사'
        assert data['address'] == '서울시 서초구'

    def test_create_valid(self, member):
        data = {
            'company_name': '신규회사',
            'phone': '031-111-2222',
            'address': '경기도 수원시',
        }
        serializer = CompanySerializer(data=data)
        assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
class TestJobNoticeSerializer:
    def test_serializer_fields(self, job_notice):
        serializer = JobNoticeSerializer(job_notice)
        data = serializer.data
        assert 'id' in data
        assert 'title' in data
        assert 'employment_type' in data
        assert 'company_name' in data
        assert 'is_premium' in data

    def test_serializer_company_name(self, job_notice):
        serializer = JobNoticeSerializer(job_notice)
        data = serializer.data
        assert data['company_name'] == '테스트회사'
        assert data['member_username'] == 'recruituser'


@pytest.mark.django_db
class TestJobNoticeCreateSerializer:
    def test_create_valid(self, company):
        data = {
            'company': company.pk,
            'employment_type': '계약직',
            'title': '프론트엔드 개발자',
            'occupations': ['개발', '웹'],
            'career_required': False,
            'payment_code': '',
        }
        serializer = JobNoticeCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_missing_required_field(self):
        data = {
            'employment_type': '정규직',
        }
        serializer = JobNoticeCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'title' in serializer.errors or 'company' in serializer.errors


@pytest.mark.django_db
class TestJobSeekerSerializer:
    def test_serializer_fields(self, job_seeker):
        serializer = JobSeekerSerializer(job_seeker)
        data = serializer.data
        assert 'id' in data
        assert 'name' in data
        assert 'resume_registered' in data
        assert 'member_username' in data

    def test_create_valid(self, member):
        data = {
            'name': '이순신',
            'gender': '남',
            'phone': '010-9999-8888',
            'email': 'lee@example.com',
            'address': '충남 아산',
        }
        serializer = JobSeekerSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
