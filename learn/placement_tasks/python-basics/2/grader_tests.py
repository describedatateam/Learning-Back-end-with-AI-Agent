import unittest

from task import BankAccount


class BankAccountTests(unittest.TestCase):
    def test_01_create(self):
        """Stores the owner, and the balance defaults to 0.0"""
        account = BankAccount("Alice")
        self.assertEqual(account.owner, "Alice")
        self.assertEqual(account.balance, 0.0)
        self.assertEqual(BankAccount("Bo", 100.0).balance, 100.0)

    def test_02_deposit(self):
        """deposit() adds to the balance"""
        account = BankAccount("Alice", 100.0)
        account.deposit(50.0)
        self.assertEqual(account.balance, 150.0)

    def test_03_withdraw(self):
        """withdraw() takes money out"""
        account = BankAccount("Alice", 100.0)
        account.withdraw(30.0)
        self.assertEqual(account.balance, 70.0)

    def test_04_insufficient_funds(self):
        """Withdrawing more than the balance raises ValueError('Insufficient funds') and keeps the money"""
        account = BankAccount("Alice", 100.0)
        with self.assertRaises(ValueError) as caught:
            account.withdraw(200.0)
        self.assertEqual(str(caught.exception), "Insufficient funds")
        self.assertEqual(account.balance, 100.0)
