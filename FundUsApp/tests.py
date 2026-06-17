from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth.models import User

from .models import Customer, Transaction


class PaystackFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='payer@example.com',
            email='payer@example.com',
            password='secret123',
        )
        self.customer = Customer.objects.create(user=self.user, pin='1234', accountBalance=Decimal('0.00'))

    @patch('FundUsApp.views.paystack_initialize')
    def test_initialize_paystack_creates_pending_transaction(self, mock_initialize):
        mock_initialize.return_value = {
            'status': True,
            'data': {
                'authorization_url': 'https://paystack.example/checkout',
                'reference': 'REF-123',
            },
        }

        self.client.force_login(self.user)

        response = self.client.post('/paystack/init/', {'amount': '2500.00'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'https://paystack.example/checkout')

        transaction = Transaction.objects.get(reference='REF-123')
        self.assertEqual(transaction.status, 'PENDING')
        self.assertEqual(transaction.amount, Decimal('2500.00'))

    @patch('FundUsApp.views.paystack_verify')
    def test_paystack_callback_marks_deposit_success(self, mock_verify):
        transaction = Transaction.objects.create(
            initiator=self.customer,
            transaction_type='DEPOSIT',
            amount=Decimal('25.00'),
            status='PENDING',
            balance_after=self.customer.accountBalance,
            reference='REF-123',
            recipient_account=self.customer.accountNumber,
            recipient_name=self.user.get_full_name() or self.user.username,
        )

        mock_verify.return_value = {
            'status': True,
            'data': {
                'data': {
                    'amount': 2500,
                }
            },
        }

        self.client.force_login(self.user)

        response = self.client.get('/callback/', {'reference': 'REF-123'})

        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        transaction.refresh_from_db()

        self.assertEqual(self.customer.accountBalance, Decimal('25.00'))
        self.assertEqual(transaction.status, 'SUCCESS')
        self.assertEqual(transaction.balance_after, Decimal('25.00'))
'''
def listCustomers():
    customers = Customer.objects.all()
    print(customers)
    for customer in customers:
        print(f'ACCOUNT NUMBER: {customer.accountNumber}')
        print(f'EMAIL: {customer.user.email}')
        print(f'PIN: {customer.user.password}')
        print(f'USERNAME: {customer.user.username}')
        print(f'CUSTOMERID: {customer.id}')

def getCustomers(id):
    try:
        customer = Customer.objects.get(id=id)
        print(f'ACCOUNT NUMBER: {customer.accountNumber}')
        print(f'EMAIL: {customer.user.email}')
        print(f'PIN: {customer.pin}')
        print(f'USERNAME: {customer.user.username}')
        print(f'CUSTOMERID: {customer.id}')
    except Customer.DoesNotExist:
        print('Customer Matching Query not found')

def UPdateCustomers(id, new_pin:str):
    try:
        if len(new_pin) != 4 or not new_pin.isdigit():
            raise Exception("PIN must be in Four Digit")
        customer = Customer.objects.get(id=id)
        customer.pin = new_pin
        customer.save()
    except Customer.DoesNotExist:
        print('Customer Matching Query not found')
    except Exception as e:
        print(e)

# UPdateCustomers('1', '2345')
getCustomers(1)
#listCustomers()

def deposit(id, amount):
    try:
        customer = Customer.objects.get(id=id)
        if amount <= 0:
            raise Exception("Amount must be greater than zero")
        customer.accountBalance += amount
        customer.save()
        transaction = Transaction.objects.create(
            initiator=customer,
            recipient_account=customer.accountNumber,
            recipient_name=customer.user.username,
            transaction_type='DEPOSIT',
            amount=amount,
            balance_after=customer.accountBalance,
            status='SUCCESS'
        )
        
        print('==========DEPOSIT RECEIPT===========')
        print(f'Customer: {customer.user.username}')
        print(f'Account Number: {customer.accountNumber}')  
        print(f'Amount Deposited: {amount}')
        print(f'New Balance: {customer.accountBalance}')
        print(f'Status: {transaction.status}')
        print('====================================')
    except Customer.DoesNotExist:
        print('Customer Matching Query not found')

deposit(1, 500)
'''