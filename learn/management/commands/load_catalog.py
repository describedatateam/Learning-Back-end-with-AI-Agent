from django.core.management.base import BaseCommand

from learn.catalog import CATALOG_FILE, load_catalog


class Command(BaseCommand):
    help = 'Create or update the job paths, skill paths, courses and chapters from learn/catalog.json.'

    def handle(self, *args, **options):
        jobs, skills = load_catalog()
        self.stdout.write(self.style.SUCCESS(f'Loaded {jobs} job paths and {skills} skill paths from {CATALOG_FILE.name}.'))
