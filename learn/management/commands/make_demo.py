"""Create (or rebuild) the demo learner for showing Describe, and print how to sign in.

    python manage.py make_demo
    python manage.py make_demo --password "choose-one"
"""
from django.core.management.base import BaseCommand

from learn import demo


class Command(BaseCommand):
    help = 'Create or rebuild the "demo" learner: a week of practice, a project, a Lab page and a public portfolio.'

    def add_arguments(self, parser):
        parser.add_argument('--password', help='Password for the demo account (a random one is made if left out).')

    def handle(self, password=None, **options):
        user, password = demo.build(password)
        self.stdout.write(f'Demo account ready. Username: {user.username}  Password: {password}')
        self.stdout.write(f'Public portfolio: /p/{demo.USERNAME}/   Case study: /case-study/')
        self.stdout.write('Run this again any time to reset the demo learner.')
