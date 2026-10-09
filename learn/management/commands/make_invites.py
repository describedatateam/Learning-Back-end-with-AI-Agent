"""Make invite codes for testers and print them with the sign-up link, ready to paste into a message.

    python manage.py make_invites 3 --note "Day 5 testers"
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from learn.models import InviteCode


class Command(BaseCommand):
    help = 'Create invite codes (one use each) and print them with the sign-up link.'

    def add_arguments(self, parser):
        parser.add_argument('count', type=int, nargs='?', default=3)
        parser.add_argument('--note', default='Testers', help='Who the codes are for, shown in admin.')

    def handle(self, count, note, **options):
        hosts = [h for h in settings.ALLOWED_HOSTS if h not in ('*', 'localhost', '127.0.0.1') and not h.startswith('.')]
        signup = f'https://{hosts[0]}/accounts/signup/' if hosts else 'http://localhost:8000/accounts/signup/'
        self.stdout.write(f'Sign-up link: {signup}')
        for _ in range(max(1, min(count, 50))):
            self.stdout.write(f'  {InviteCode.objects.create(note=note).code}')
        self.stdout.write('Each code works once. See or switch them off in Admin > Invite codes.')
