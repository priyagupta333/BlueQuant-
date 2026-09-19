from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import UserProfile


class Command(BaseCommand):
    help = "Seed demo users for ISRO admin and Field Officer roles."

    def handle(self, *args, **options):
        # ISRO Admin
        isro_email = "isro_admin@example.com"
        isro_password = "isro12345"
        isro_user, created = User.objects.get_or_create(
            username=isro_email,
            defaults={"email": isro_email}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created user {isro_email}"))
        isro_user.set_password(isro_password)
        isro_user.is_staff = True
        isro_user.save()
        UserProfile.objects.update_or_create(user=isro_user, defaults={"role": "isro_admin"})

        # Field Officer
        field_email = "field_officer@example.com"
        field_password = "field12345"
        field_user, created = User.objects.get_or_create(
            username=field_email,
            defaults={"email": field_email}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created user {field_email}"))
        field_user.set_password(field_password)
        field_user.save()
        UserProfile.objects.update_or_create(user=field_user, defaults={"role": "field_officer"})

        self.stdout.write(self.style.SUCCESS("Seeded: isro_admin@example.com / field_officer@example.com"))
