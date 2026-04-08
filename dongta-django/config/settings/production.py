from .base import *
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration

DEBUG = False

# 운영 환경 호스트 설정
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[
    'dongta.com',
    'www.dongta.com',
    'dongta.theuit.info',
    'www.dongta.theuit.info',
    'api.dongta.theuit.info',
    'testserver',  # Django test client
    'localhost',
    '127.0.0.1',
    '52.79.148.197',  # AWS EC2 IP
])

# HTTPS 보안 강화
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cloudflare SSL 무한 리다이렉션 방지
# Cloudflare Full Strict SSL을 사용하는 경우, X-Forwarded-Proto 헤더를 신뢰
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# 또는 Cloudflare CF-Visitor 헤더 사용 (더 안전)
# SECURE_PROXY_SSL_HEADER = ('HTTP_CF_VISITOR', '{"scheme":"https"}')

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # True 시 일부 브라우저에서 CSRF 쿠키 전송 문제 발생
CSRF_COOKIE_SAMESITE = 'Lax'

# Cloudflare 도메인 신뢰 설정 (CSRF 토큰 검증)
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[
    'https://dongta.theuit.info',
    'https://www.dongta.theuit.info',
    'https://www.dongta.com',
    'https://dongta.com',
])

# 세션 설정
# cached_db: Redis 캐시 우선 조회 → 만료/미스 시 DB 폴백 (Admin 세션 안정성)
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 60 * 60 * 8   # 8시간 (28800초)
SESSION_SAVE_EVERY_REQUEST = True   # 요청마다 만료 시간 갱신

# S3 파일 스토리지
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# Sentry 연동
SENTRY_DSN = env('SENTRY_DSN', default=None)
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=env.float('SENTRY_TRACES_SAMPLE_RATE', default=0.1),
        send_default_pii=True,
        environment='production',
    )

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.sync': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.payment': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Slow query 로깅 임계값 (ms)
# PostgreSQL: log_min_duration_statement = 100ms
SLOW_QUERY_LOG_THRESHOLD_MS = env.int('SLOW_QUERY_LOG_THRESHOLD_MS', default=100)
