import pytest
from apps.mypage.models import MyFolder, MyData
from apps.accounts.models import Member


@pytest.fixture
def member(db):
    return Member.objects.create_user(
        username='mypageuser',
        email='mypage@example.com',
        name='마이페이지유저',
        password='MypagePass!1',
    )


@pytest.fixture
def folder(db, member):
    return MyFolder.objects.create(
        member=member,
        name='찜 폴더 1',
    )


@pytest.mark.django_db
class TestMyFolderModel:
    def test_folder_creation(self, folder, member):
        assert folder.name == '찜 폴더 1'
        assert folder.member == member
        assert folder.is_deleted is False

    def test_folder_str(self, folder, member):
        assert str(folder) == f'{member.username} - 찜 폴더 1'

    def test_folder_soft_delete(self, folder):
        folder.soft_delete()
        folder.refresh_from_db()
        assert folder.is_deleted is True

    def test_folder_default_description(self, member):
        folder = MyFolder.objects.create(member=member, name='새폴더')
        assert folder.description == ''


@pytest.mark.django_db
class TestMyDataModel:
    def test_data_creation(self, folder, member):
        item = MyData.objects.create(
            folder=folder,
            member=member,
            content_type='business',
            object_id=1,
        )
        assert item.content_type == 'business'
        assert item.object_id == 1
        assert item.folder == folder

    def test_data_str(self, folder, member):
        item = MyData.objects.create(
            folder=folder,
            member=member,
            content_type='recruit',
            object_id=5,
        )
        assert str(item) == f'{folder.name} - recruit:5'

    def test_data_soft_delete(self, folder, member):
        item = MyData.objects.create(
            folder=folder,
            member=member,
            content_type='business',
            object_id=2,
        )
        item.soft_delete()
        item.refresh_from_db()
        assert item.is_deleted is True
