from django.db import transaction

from sandbox.models import Account, TransferLog


class InsufficientFunds(Exception):
    pass


def transfer(source_id, destination_id, amount):
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise ValueError("amount must be a positive number of cents")
    if source_id == destination_id:
        raise ValueError("cannot transfer to the same account")

    with transaction.atomic():
        source = Account.objects.select_for_update().get(pk=source_id)
        destination = Account.objects.select_for_update().get(pk=destination_id)
        if source.balance < amount:
            raise InsufficientFunds(f"{source.owner} has only {source.balance} cents")

        source.balance -= amount
        destination.balance += amount
        source.save()
        destination.save()
        return TransferLog.objects.create(source=source, destination=destination, amount=amount)
