from django.test import TestCase
from django.contrib.auth import get_user_model
from board.models import Post, Comment, PostLike, PostCategory

User = get_user_model()


class PostModelTest(TestCase):
    """게시글 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.post = Post.objects.create(
            category=PostCategory.FREE,
            title='Test Post',
            content='Test Content',
            member=self.user
        )

    def test_post_creation(self):
        """게시글 생성 테스트"""
        self.assertEqual(self.post.title, 'Test Post')
        self.assertEqual(self.post.member.username, 'testuser')
        self.assertEqual(self.post.category, PostCategory.FREE)
        self.assertEqual(self.post.view_count, 0)
        self.assertEqual(self.post.like_count, 0)

    def test_post_str(self):
        """게시글 문자열 표현 테스트"""
        self.assertEqual(str(self.post), '[자유게시판] Test Post')

    def test_post_categories(self):
        """모든 게시판 카테고리 테스트"""
        categories = [
            PostCategory.NOTICE,
            PostCategory.FREE,
            PostCategory.QNA,
            PostCategory.GALLERY
        ]
        for category in categories:
            post = Post.objects.create(
                category=category,
                title=f'Post {category}',
                content='Content',
                member=self.user
            )
            self.assertEqual(post.category, category)


class CommentModelTest(TestCase):
    """댓글 모델 테스트"""

    def setUp(self):
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

    def test_comment_creation(self):
        """댓글 생성 테스트"""
        self.assertEqual(self.comment.content, 'Test Comment')
        self.assertEqual(self.comment.post.id, self.post.id)
        self.assertIsNone(self.comment.parent)

    def test_comment_reply(self):
        """대댓글 생성 테스트"""
        reply = Comment.objects.create(
            post=self.post,
            member=self.user,
            content='Test Reply',
            parent=self.comment
        )
        self.assertEqual(reply.parent.id, self.comment.id)
        self.assertEqual(reply.post.id, self.post.id)


class PostLikeModelTest(TestCase):
    """게시글 추천 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.post = Post.objects.create(
            category=PostCategory.FREE,
            title='Test Post',
            content='Test Content',
            member=self.user
        )

    def test_like_creation(self):
        """추천 생성 테스트"""
        like = PostLike.objects.create(post=self.post, member=self.user)
        self.assertEqual(like.post.id, self.post.id)
        self.assertEqual(like.member.id, self.user.id)

    def test_unique_like(self):
        """중복 추천 방지 테스트"""
        PostLike.objects.create(post=self.post, member=self.user)
        with self.assertRaises(Exception):
            PostLike.objects.create(post=self.post, member=self.user)
