from unittest import mock

from django.test import TestCase

from banking import InsufficientFunds, transfer
from sandbox.models import Account, TransferLog


class TransferTests(TestCase):
    def setUp(self):
        self.ada = Account.objects.create(owner="Ada", balance=10_000)
        self.bob = Account.objects.create(owner="Bob", balance=500)

    def balances(self):
        self.ada.refresh_from_db()
        self.bob.refresh_from_db()
        return self.ada.balance, self.bob.balance

    def test_01_moves_money(self):
        """A valid transfer moves the money"""
        transfer(self.ada.id, self.bob.id, 2_500)
        self.assertEqual(self.balances(), (7_500, 3_000))

    def test_02_logs_transfer(self):
        """A valid transfer creates and returns one TransferLog"""
        log = transfer(self.ada.id, self.bob.id, 100)
        self.assertIsInstance(log, TransferLog)
        self.assertEqual(TransferLog.objects.count(), 1)
        self.assertEqual((log.source_id, log.destination_id, log.amount), (self.ada.id, self.bob.id, 100))

    def test_03_bad_amount(self):
        """Zero, negative and non-integer amounts raise ValueError"""
        for amount in [0, -50, 12.5, "100"]:
            with self.assertRaises(ValueError, msg=f"amount={amount!r}"):
                transfer(self.ada.id, self.bob.id, amount)
        self.assertEqual(self.balances(), (10_000, 500))

    def test_04_same_account(self):
        """Transferring to the same account raises ValueError"""
        with self.assertRaises(ValueError):
            transfer(self.ada.id, self.ada.id, 100)

    def test_05_insufficient_funds(self):
        """Overdrawing raises InsufficientFunds and changes nothing"""
        with self.assertRaises(InsufficientFunds):
            transfer(self.bob.id, self.ada.id, 501)
        self.assertEqual(self.balances(), (10_000, 500))
        self.assertEqual(TransferLog.objects.count(), 0)

    def test_06_missing_destination_rolls_back(self):
        """A missing destination raises DoesNotExist and changes nothing"""
        with self.assertRaises(Account.DoesNotExist):
            transfer(self.ada.id, 999_999, 100)
        self.assertEqual(self.balances(), (10_000, 500), "The source was charged but the transfer failed!")

    def test_07_failure_at_last_step_rolls_back(self):
        """If writing the log fails, both balance changes are rolled back"""
        with mock.patch.object(TransferLog.objects, "create", side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                transfer(self.ada.id, self.bob.id, 1_000)
        self.assertEqual(self.balances(), (10_000, 500), "Money moved even though the transfer failed. Use transaction.atomic()")
