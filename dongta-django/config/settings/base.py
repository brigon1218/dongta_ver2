"""
dongta.com Django 기본 설정
"""
from pathlib import Path
from datetime import timedelta
import environ

# PyMySQL을 MySQL 백엔드 대신 사용 (mysqlclient 대체)
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# =============================================================================
# 환경 설정 (Environ)
# =============================================================================
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)
# OS에 관계없이 .env 파일을 프로젝트 루트에서 로드
environ.Env.read_env(BASE_DIR / '.env')

# 프로젝트 루트 기반 경로 도우미
def root_path(*paths):
    return BASE_DIR.joinpath(*paths)

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Application definition
DJANGO_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'jazzmin',  # Must come before django.contrib.admin
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
    'django_celery_beat',
    'django_prometheus',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.business114',
    'apps.recruit',
    'apps.payment',
    'apps.board',
    'apps.mypage',
    'apps.sync',
    'apps.monitoring',  # Phase 2.1: 모니터링
    'core',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'apps.accounts.middleware.RequestIDMiddleware',  # Phase 2.1: Request ID
    'apps.monitoring.middleware.RoutingStatsMiddleware',  # Phase 2.1: 통계
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'apps.accounts.middleware.SessionBridgeMiddleware',  # Phase 2.1: 세션 브리지 (인증 전)
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.CacheHitHeaderMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database - PostgreSQL
DATABASES = {
    'default': {
        **env.db('DATABASE_URL'),
        'CONN_MAX_AGE': env.int('DB_CONN_MAX_AGE', default=60),  # Connection pooling: 60초
        'OPTIONS': {
            'connect_timeout': env.int('DB_CONNECT_TIMEOUT', default=10),
            'options': '-c statement_timeout=30000',  # 쿼리 타임아웃 30초 (ms 단위)
        }
    }
}

# MySQL (하이브리드 기간 레거시 동기화)
if env('MYSQL_DATABASE_URL', default=None):
    DATABASES['legacy'] = {
        **env.db('MYSQL_DATABASE_URL'),
        'CONN_MAX_AGE': env.int('DB_CONN_MAX_AGE', default=60),
    }

# 커스텀 유저 모델
AUTH_USER_MODEL = 'accounts.Member'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# 패스워드 해셔 (Argon2id를 기본으로 사용, MD5 레거시 지원)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'apps.accounts.hashers.LegacyMD5PasswordHasher',
]

# Internationalization
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True

# Static & Media
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# DRF (Django REST Framework)
# =============================================================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# =============================================================================
# JWT 설정
# =============================================================================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=env.int('JWT_ACCESS_LIFETIME_HOURS', default=1)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=env.int('JWT_REFRESH_LIFETIME_DAYS', default=7)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# =============================================================================
# CORS
# =============================================================================
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
CORS_ALLOW_CREDENTIALS = True

# =============================================================================
# Celery (비동기 작업)
# =============================================================================
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default=env('REDIS_URL', default='redis://localhost:6379/0'))
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default=env('REDIS_URL', default='redis://localhost:6379/0'))
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Seoul'
CELERY_ENABLE_UTC = True
CELERY_RESULT_EXPIRES = 86400
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SOFT_TIME_LIMIT = 300
CELERY_TASK_TIME_LIMIT = 360

# Celery Beat Schedule (주기적 작업)
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'cleanup-expired-password-reset-tokens': {
        'task': 'apps.accounts.tasks.cleanup_expired_password_reset_tokens',
        'schedule': crontab(minute=0),  # 매시간
    },
    'poll-pending-events': {
        'task': 'apps.sync.tasks.poll_pending_events',
        'schedule': crontab(minute='*/5'),  # 5분마다 (PostgreSQL 이벤트 폴링)
    },
    'process-php-events': {
        'task': 'apps.sync.tasks.process_php_events',
        'schedule': crontab(minute='*/5'),  # 5분마다 (MySQL 이벤트 폴링)
    },
    'verify-sync-integrity': {
        'task': 'apps.sync.tasks.verify_sync_integrity',
        'schedule': crontab(minute=0),  # 매시간 (동기화 무결성 검증)
    },
    'clean-old-event-logs': {
        'task': 'apps.sync.tasks.clean_old_event_logs',
        'schedule': crontab(hour=2, minute=0),  # 매일 오전 2시 (7일 이상 된 로그 정리)
    },
}

# MySQL 동기화 설정 (하이브리드 기간)
SYNC_BATCH_SIZE = env.int('SYNC_BATCH_SIZE', default=500)
SYNC_STALE_HOURS = env.int('SYNC_STALE_HOURS', default=1)

# =============================================================================
# Cache (Redis) - django-redis 백엔드 사용 (cache.delete_pattern() 지원)
# =============================================================================
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,  # Redis 장애 시 캐시 오류가 앱 전체를 멈추지 않도록
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
            },
        },
        'KEY_PREFIX': 'dongta',
    }
}

# =============================================================================
# Email
# =============================================================================
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@dongta.com')

# =============================================================================
# AWS S3
# =============================================================================
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = env('AWS_S3_BUCKET_NAME', default='')
AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME', default='ap-northeast-2')
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
AWS_DEFAULT_ACL = 'private'

# =============================================================================
# Jazzmin (Django Admin UI)
# =============================================================================
JAZZMIN_SETTINGS = {
    "site_title": "dongta.com 관리자",
    "site_header": "dongta.com",
    "site_brand": "dongta",
    "welcome_sign": "dongta.com 관리자 페이지에 오신 것을 환영합니다",
    "copyright": "dongta.com 2024. 모든 권리 보유",
    "search_model": ["auth.User", "accounts.Member"],
    "topmenu_links": [
        {"name": "홈", "url": "admin:index", "permissions": ["auth.add_user"]},
        {"name": "API 문서", "url": "/api/schema/swagger/", "permissions": ["auth.add_user"]},
        {"name": "사이트", "url": "/", "new_window": True},
    ],
    "usermenu_links": [
        {
            "model": "accounts.member"
        }
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "accounts.Member": "fas fa-user-tie",
        "accounts.MemberDormant": "fas fa-user-slash",
        "accounts.PasswordResetToken": "fas fa-key",
        "business114.Business": "fas fa-store",
        "recruit.Company": "fas fa-building",
        "recruit.JobNotice": "fas fa-briefcase",
        "recruit.JobSeeker": "fas fa-user-graduate",
        "payment.PaymentHistory": "fas fa-credit-card",
        "board.Post": "fas fa-newspaper",
        "board.Comment": "fas fa-comments",
        "board.PostLike": "fas fa-thumbs-up",
    },
    "default_icon_parents": "fas fa-chevron-right",
    "default_icon_children": "fas fa-arrow-right",
    "show_ui_builder": False,
    "changeform_format": "single",
    "language_chooser": False,
}

# =============================================================================
# API 문서 (drf-spectacular)
# =============================================================================
SPECTACULAR_SETTINGS = {
    'TITLE': 'dongta.com API',
    'DESCRIPTION': 'dongta.com REST API 문서',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# =============================================================================
# Rate Limiting (django-ratelimit)
# =============================================================================
RATELIMIT_USE_CACHE = 'default'

# =============================================================================
# Danal 결제
# =============================================================================
DANAL_MERCHANT_ID = env('DANAL_MERCHANT_ID', default='')
DANAL_MERCHANT_KEY = env('DANAL_MERCHANT_KEY', default='')
DANAL_RETURN_URL = env('DANAL_RETURN_URL', default='')

# =============================================================================
# 프론트엔드 설정
# =============================================================================
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:3000')

# =============================================================================
# Phase 2.1: PHP ↔ Django 하이브리드 연동
# =============================================================================
BRIDGE_AUTH_ENABLED = env('BRIDGE_AUTH_ENABLED', default=True)
BRIDGE_CACHE_TTL = env('BRIDGE_CACHE_TTL', default=900)  # 15분
BRIDGE_JWT_TTL_MINUTES = env('BRIDGE_JWT_TTL_MINUTES', default=60)  # 1시간
# Design S13: PHP 세션 저장소 유형 (file | mysql | redis)
PHP_SESSION_STORAGE = env('PHP_SESSION_STORAGE', default='mysql')
# Design S13: 이벤트 로깅 활성화 여부
EVENT_LOG_ENABLED = env('EVENT_LOG_ENABLED', default=True)
# Design S13: 모니터링 API 어드민 전용 여부
MONITORING_ADMIN_ONLY = env('MONITORING_ADMIN_ONLY', default=True)

# Legacy DB 연결 (MySQL)
DATABASES['legacy'] = {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': env('LEGACY_DB_NAME', default='dongta_legacy'),
    'USER': env('LEGACY_DB_USER', default='root'),
    'PASSWORD': env('LEGACY_DB_PASSWORD', default=''),
    'HOST': env('LEGACY_DB_HOST', default='localhost'),
    'PORT': env('LEGACY_DB_PORT', default='3306'),
    'OPTIONS': {
        'charset': 'utf8mb4',
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
    }
}
