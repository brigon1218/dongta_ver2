import pytest
from django.utils import timezone
from apps.recruit.models import Company, JobNotice, JobSeeker
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
        email='company@example.com',
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
        birth_date='1990-01-15',
        gender='남',
        phone='010-1234-5678',
        email='hong@example.com',
        address='서울시 강북구',
        resume_registered=True,
    )


@pytest.mark.django_db
class TestCompanyModel:
    def test_company_creation(self, company):
        assert company.company_name == '테스트회사'
        assert company.is_deleted is False

    def test_company_str(self, company):
        assert str(company) == '테스트회사'

    def test_company_soft_delete(self, company):
        company.soft_delete()
        company.refresh_from_db()
        assert company.is_deleted is True

    def test_company_has_notice_default(self, member):
        co = Company.objects.create(
            member=member,
            company_name='새회사',
            address='부산시',
        )
        assert co.has_notice is False


@pytest.mark.django_db
class TestJobNoticeModel:
    def test_job_notice_creation(self, job_notice):
        assert job_notice.title == '백엔드 개발자 채용'
        assert job_notice.is_approved is True
        assert job_notice.is_premium is False

    def test_job_notice_str(self, job_notice):
        expected = f'백엔드 개발자 채용 (테스트회사)'
        assert str(job_notice) == expected

    def test_job_notice_premium_fields_default(self, job_notice):
        assert job_notice.is_premium is False
        assert job_notice.premium_start_date is None
        assert job_notice.premium_end_date is None

    def test_job_notice_occupations_json(self, job_notice):
        assert isinstance(job_notice.occupations, list)
        assert '개발' in job_notice.occupations

    def test_job_notice_soft_delete(self, job_notice):
        job_notice.soft_delete()
        job_notice.refresh_from_db()
        assert job_notice.is_deleted is True


@pytest.mark.django_db
class TestJobSeekerModel:
    def test_job_seeker_creation(self, job_seeker):
        assert job_seeker.name == '홍길동'
        assert job_seeker.resume_registered is True

    def test_job_seeker_str(self, job_seeker, member):
        expected = f'홍길동 ({member.username})'
        assert str(job_seeker) == expected

    def test_job_seeker_soft_delete(self, job_seeker):
        job_seeker.soft_delete()
        job_seeker.refresh_from_db()
        assert job_seeker.is_deleted is True
