from django.db import models


class Book(models.Model):
    title = models.CharField(max_length=200)
    # TODO 1: author: a CharField with max_length=100
    # TODO 2: published_year: an optional PositiveIntegerField (null=True, blank=True)
    # TODO 3: is_available: a BooleanField that defaults to True
    # TODO 4: created_at: a DateTimeField set automatically (auto_now_add=True)

    # TODO 5: def __str__(self): return "<title> by <author>"

    # TODO 6: class Meta: with ordering = ["title"]

    # TODO 7: def is_classic(self): True only if published_year is not None and < 1950
