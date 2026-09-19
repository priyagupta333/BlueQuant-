from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Normalize Project.title to remove appended location suffix (keeps the project name/species only)."

    def handle(self, *args, **options):
        from api.models import Project
        updated = 0
        checked = 0
        for p in Project.objects.all().only('id', 'title', 'location', 'species'):
            checked += 1
            title = (p.title or '').strip()
            location = (p.location or '').strip()
            species = (p.species or '').strip()
            if not title:
                # If empty, prefer species; else fallback to generic
                new_title = species or f"Project #{p.id}"
            else:
                new_title = title
                # Case-insensitive check for pattern "<something> - <location>"
                if ' - ' in title and location:
                    left, sep, right = title.rpartition(' - ')
                    if right.strip().lower() == location.lower():
                        # If left matches species, prefer species; else keep left as provided name
                        new_title = left.strip() or title
                # Also handle exact title == location (rare)
                if location and new_title.strip().lower() == location.lower():
                    new_title = species or new_title
            if new_title != title:
                p.title = new_title
                p.save(update_fields=['title'])
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Normalized titles for {updated} of {checked} project(s)."))
