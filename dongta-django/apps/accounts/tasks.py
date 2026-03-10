from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import Member, PasswordResetToken


@shared_task(bind=True, max_retries=3)
def send_password_reset_email(self, member_id, email, token):
    """비밀번호 재설정 이메일 발송"""
    try:
        member = Member.objects.get(id=member_id, is_deleted=False)

        # 이메일 본문 생성
        reset_url = f"{settings.FRONTEND_URL}/password/reset/confirm?token={token}"
        context = {
            'member_name': member.name,
            'reset_url': reset_url,
            'expires_hours': 1,
        }

        html_message = render_to_string('accounts/password_reset_email.html', context)
        plain_message = strip_tags(html_message)

        # 이메일 발송
        msg = EmailMultiAlternatives(
            subject='[dongta.com] 비밀번호 재설정',
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email]
        )
        msg.attach_alternative(html_message, "text/html")
        msg.send()

        return f"Password reset email sent to {email}"

    except Member.DoesNotExist:
        return f"Member {member_id} not found"
    except Exception as exc:
        # 재시도 (최대 3회, 10초 간격)
        raise self.retry(exc=exc, countdown=10)


@shared_task
def cleanup_expired_password_reset_tokens():
    """만료된 비밀번호 재설정 토큰 정리 (매시간 실행)"""
    from django.utils import timezone
    expired_count, _ = PasswordResetToken.objects.filter(
        is_used=False,
        expires_at__lt=timezone.now()
    ).delete()
    return f"Deleted {expired_count} expired tokens"
