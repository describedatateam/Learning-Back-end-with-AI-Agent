from django.db import models


class Account(models.Model):
    owner = models.CharField(max_length=100)
    balance = models.IntegerField(default=0)  # in cents: never use floats for money

    def __str__(self):
        return f"{self.owner}: {self.balance}"


class TransferLog(models.Model):
    source = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="+")
    destination = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="+")
    amount = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
