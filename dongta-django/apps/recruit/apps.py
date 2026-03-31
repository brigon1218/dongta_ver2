from django.apps import AppConfig


class RecruitConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.recruit'

    def ready(self):
        """Signal 등록"""
        import apps.recruit.signals  # noqa
