from django.contrib.auth.models import User

from sandbox.models import Note


def register_user(username, email, password):
    if User.objects.filter(username__iexact=username).exists():
        raise ValueError("username already taken")
    return User.objects.create_user(username=username, email=email, password=password)


def notes_for(user):
    return Note.objects.filter(owner=user).order_by("-created_at")


def create_note(user, text):
    return Note.objects.create(owner=user, text=text)
