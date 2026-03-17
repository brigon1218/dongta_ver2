import pytest
from apps.business114.models import Business, BusinessType
from apps.business114.serializers import (
    BusinessListSerializer,
    BusinessDetailSerializer,
    BusinessCreateSerializer,
)
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
        address='서울시 강남구',
        industry_type=1,
        items=[1, 2],
        keywords='테스트,키워드',
        is_approved=True,
    )


@pytest.mark.django_db
class TestBusinessListSerializer:
    def test_list_serializer_fields(self, business):
        serializer = BusinessListSerializer(business)
        data = serializer.data
        assert 'id' in data
        assert 'corp_name' in data
        assert 'address' in data
        assert 'industry_type' in data
        assert 'business_type' in data
        assert 'business_type_display' in data
        assert 'view_count' in data

    def test_list_serializer_values(self, business):
        serializer = BusinessListSerializer(business)
        data = serializer.data
        assert data['corp_name'] == '테스트업체'
        assert data['address'] == '서울시 강남구'
        assert data['business_type_display'] == '매장'


@pytest.mark.django_db
class TestBusinessDetailSerializer:
    def test_detail_serializer_fields(self, business):
        serializer = BusinessDetailSerializer(business)
        data = serializer.data
        assert 'member' in data
        assert 'member_username' in data
        assert 'description' in data
        assert 'location_info' in data
        assert 'total_payment' in data

    def test_detail_serializer_member_username(self, business):
        serializer = BusinessDetailSerializer(business)
        data = serializer.data
        assert data['member_username'] == 'bizuser'


@pytest.mark.django_db
class TestBusinessCreateSerializer:
    def test_create_serializer_valid(self):
        data = {
            'business_type': BusinessType.STORE,
            'corp_name': '새업체',
            'phone': '031-555-6789',
            'address': '경기도 수원시',
            'industry_type': 2,
            'items': [5, 6],
        }
        serializer = BusinessCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_serializer_invalid_industry_type(self):
        data = {
            'business_type': BusinessType.STORE,
            'corp_name': '잘못된업체',
            'address': '서울',
            'industry_type': 99,
            'items': [],
        }
        serializer = BusinessCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'industry_type' in serializer.errors
