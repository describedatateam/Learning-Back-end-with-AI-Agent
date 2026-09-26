from django.db import transaction

from sandbox.models import Account, TransferLog


class InsufficientFunds(Exception):
    pass


def transfer(source_id, destination_id, amount):
    # The tests pass in two account ids and an amount in cents.
    # This code moves the money, but it isn't safe yet. Keep its steps, and:
    # TODO 1: raise ValueError if amount isn't an int, or is 0 or less
    # TODO 2: raise ValueError if source_id == destination_id
    # TODO 3: put all the database code below inside `with transaction.atomic():`
    # TODO 4: fetch BOTH accounts first, with Account.objects.select_for_update().get(pk=...)
    # TODO 5: raise InsufficientFunds if the source balance is less than amount
    # TODO 6: then subtract, add and save both accounts
    # TODO 7: keep TransferLog.objects.create(...) as the last step, inside the block
    source = Account.objects.get(pk=source_id)
    source.balance -= amount
    source.save()

    destination = Account.objects.get(pk=destination_id)
    destination.balance += amount
    destination.save()

    return TransferLog.objects.create(source=source, destination=destination, amount=amount)
