from django.core.management.base import BaseCommand
from django.db.models import Q

class Command(BaseCommand):
    help = "Backfill Project.title from legacy fields if empty."

    def handle(self, *args, **options):
        from api.models import Project
        updated = 0
        # Find projects with empty or null title
        qs = Project.objects.filter(Q(title__isnull=True) | Q(title=""))
        for p in qs:
            # Try to infer a sensible title from other fields
            fallback = None
            # Historically, 'name' existed; if data was migrated via dump/load, it may linger in __dict__
            if hasattr(p, 'name') and getattr(p, 'name'):
                fallback = getattr(p, 'name')
            if not fallback:
                # Compose from species/location as last resort
                parts = []
                if getattr(p, 'species', None):
                    parts.append(str(p.species))
                if getattr(p, 'location', None):
                    parts.append(str(p.location))
                if parts:
                    fallback = " - ".join(parts)
                else:
                    fallback = f"Project #{p.id}"
            p.title = fallback
            p.save(update_fields=["title"])
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"Backfilled titles for {updated} project(s)."))
