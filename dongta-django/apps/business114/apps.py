from django.apps import AppConfig


class Business114Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.business114'

    def ready(self):
        """Signal 등록"""
        import apps.business114.signals  # noqa
