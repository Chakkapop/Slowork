from django.apps import AppConfig


class SloworkConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "slowork"

    def ready(self) -> None:
        pass