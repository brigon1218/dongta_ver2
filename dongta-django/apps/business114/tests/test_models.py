import pytest
from apps.business114.models import Business, BusinessType
from apps.accounts.models import Member


@pytest.fixture
def member(db):
    return Member.objects.create_user(
        username='bizuser',
        email='biz@example.com',
        name='업체유저',
        password='BizPass!1',
    )


@pytest.fixture
def business(db, member):
    return Business.objects.create(
        member=member,
        business_type=BusinessType.STORE,
        corp_name='테스트업체',
        phone='02-1234-5678',
        address='서울시 강남구 테스트로 1',
        industry_type=1,
        items=[1, 2, 3],
        is_approved=True,
    )


@pytest.mark.django_db
class TestBusinessModel:
    def test_business_creation(self, business):
        assert business.corp_name == '테스트업체'
        assert business.business_type == BusinessType.STORE
        assert business.is_approved is True
        assert business.is_deleted is False

    def test_business_str(self, business):
        expected = f'테스트업체 (업종:{business.industry_type})'
        assert str(business) == expected

    def test_business_default_view_count(self, member):
        biz = Business.objects.create(
            member=member,
            business_type=BusinessType.FACTORY,
            corp_name='공장업체',
            address='경기도 성남시 분당구',
            industry_type=2,
        )
        assert biz.view_count == 0
        assert biz.total_payment == 0

    def test_business_soft_delete(self, business):
        assert business.is_deleted is False
        business.soft_delete()
        business.refresh_from_db()
        assert business.is_deleted is True
        assert business.deleted_at is not None

    def test_business_items_json_field(self, business):
        assert isinstance(business.items, list)
        assert 1 in business.items
        assert 2 in business.items

    def test_business_type_choices(self):
        assert BusinessType.FACTORY == 1
        assert BusinessType.STORE == 2

    def test_business_unapproved_by_default(self, member):
        biz = Business.objects.create(
            member=member,
            business_type=BusinessType.STORE,
            corp_name='미승인업체',
            address='서울시 종로구',
            industry_type=3,
        )
        assert biz.is_approved is False
