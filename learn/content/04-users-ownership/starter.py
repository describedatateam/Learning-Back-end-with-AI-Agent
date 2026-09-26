from django.contrib.auth.models import User

from sandbox.models import Note


def register_user(username, email, password):
    # The tests call this, for example register_user("ada", "ada@example.com", "s3cret-pass!").
    # TODO 1: if a user with this username exists (ignoring case, username__iexact),
    #         raise ValueError("username already taken")
    # TODO 2: create_user hashes the password; create (below) does NOT. Swap it.
    return User.objects.create(username=username, email=email, password=password)


def notes_for(user):
    # TODO 4: keep only notes whose owner is `user` (filter instead of all)
    # TODO 5: newest first: order by created_at, with a "-"
    return Note.objects.all()


def create_note(user, text):
    # TODO 3: create and return a Note with owner=user and text=text
    raise NotImplementedError("create_note is not written yet")
