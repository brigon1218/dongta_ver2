from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from board.models import Post, Comment, PostCategory

User = get_user_model()


class PostViewSetTest(APITestCase):
    """게시글 ViewSet 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.admin = User.objects.create_superuser(username='admin', password='adminpass123')
        self.post = Post.objects.create(
            category=PostCategory.FREE,
            title='Test Post',
            content='Test Content',
            member=self.user
        )

    def test_list_posts(self):
        """게시글 목록 조회 테스트"""
        response = self.client.get('/api/v1/board/posts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_post(self):
        """게시글 상세 조회 테스트"""
        response = self.client.get(f'/api/v1/board/posts/{self.post.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 조회수 증가 확인
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, 1)

    def test_create_post_authenticated(self):
        """인증 사용자 게시글 작성 테스트"""
        self.client.force_authenticate(user=self.user)
        data = {
            'category': PostCategory.FREE,
            'title': 'New Post',
            'content': 'New Content',
            'is_pinned': False
        }
        response = self.client.post('/api/v1/board/posts/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_notice_staff_only(self):
        """공지사항 Staff 전용 작성 테스트"""
        # 일반 사용자는 공지사항 작성 불가
        self.client.force_authenticate(user=self.user)
        data = {
            'category': PostCategory.NOTICE,
            'title': 'Notice Post',
            'content': 'Notice Content',
            'is_pinned': False
        }
        response = self.client.post('/api/v1/board/posts/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Admin 사용자는 공지사항 작성 가능
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/board/posts/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_like_toggle(self):
        """추천 토글 테스트"""
        self.client.force_authenticate(user=self.user)

        # 추천 등록
        response = self.client.post(f'/api/v1/board/posts/{self.post.id}/like/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.like_count, 1)

        # 추천 취소
        response = self.client.post(f'/api/v1/board/posts/{self.post.id}/like/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.like_count, 0)

    def test_filter_by_category(self):
        """카테고리 필터 테스트"""
        response = self.client.get(f'/api/v1/board/posts/?category={PostCategory.FREE}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_posts(self):
        """게시글 검색 테스트"""
        response = self.client.get('/api/v1/board/posts/?q=Test')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CommentViewSetTest(APITestCase):
    """댓글 ViewSet 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.post = Post.objects.create(
            category=PostCategory.FREE,
            title='Test Post',
            content='Test Content',
            member=self.user
        )
        self.comment = Comment.objects.create(
            post=self.post,
            member=self.user,
            content='Test Comment'
        )

    def test_create_comment(self):
        """댓글 작성 테스트"""
        self.client.force_authenticate(user=self.user)
        data = {
            'post': self.post.id,
            'content': 'New Comment'
        }
        response = self.client.post('/api/v1/board/comments/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_delete_comment(self):
        """댓글 삭제 테스트"""
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(f'/api/v1/board/comments/{self.comment.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_deleted)
