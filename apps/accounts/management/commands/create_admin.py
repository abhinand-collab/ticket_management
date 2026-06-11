from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Create default admin user"

    def handle(self, *args, **kwargs):
        User = get_user_model()

        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.WARNING(
                    "Superuser already exists. Skipping."
                )
            )
            return

        User.objects.create_superuser(
            username="admin",
            email="admin@gmail.com",
            password="admin",
)

        self.stdout.write(
            self.style.SUCCESS(
                "Superuser created successfully."
            )
        )