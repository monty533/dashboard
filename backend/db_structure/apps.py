from django.apps import AppConfig


class DbStructureConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'db_structure'

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save

        from .models import UserProfile

        user_model = get_user_model()

        def create_user_profile(sender, instance, created, **kwargs):
            if created:
                UserProfile.objects.get_or_create(user=instance)

        post_save.connect(
            create_user_profile,
            sender=user_model,
            dispatch_uid='db_structure.create_user_profile',
        )
