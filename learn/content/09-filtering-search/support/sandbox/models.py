from django.db import models


class Task(models.Model):
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=20, default="todo")      # todo | in_progress | done
    priority = models.CharField(max_length=10, default="medium")  # low | medium | high
    due_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.title
