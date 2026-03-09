from django.apps import AppConfig


class SyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sync'
    verbose_name = 'MySQL-PostgreSQL 동기화'

    def ready(self) -> None:
        """앱 초기화 시 시그널 등록"""
        pass
