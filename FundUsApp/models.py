from django.db import models
from random import randint
from django.contrib.auth.models import User
from decimal import Decimal

def generateAccountNumber():
    account_number = '59'
    account_number = account_number + str(randint(10000000, 99999999))
    return account_number

GENDER = (
    ('M', 'MALE'),
    ('F', 'FEMALE'),
    ('U', 'UNSPECIFIED')
)

TRANSACTION_TYPE = (
    ('DEPOSIT', 'Deposit'),
    ('WITHDRAWAL', 'Withdrawal'),
    ('TRANSFER', 'Transfer'),
)

TRANSACTION_STATUS = (
    ('PENDING', 'Pending'),
    ('SUCCESS', 'Success'),
    ('FAILED', 'Failed'),
    ('REVERSED', 'Reversed'),
)

# Create your models here.
class Customer(models.Model):
    user = models.OneToOneField(to=User, on_delete=models.CASCADE)
    bvn = models.CharField(max_length=11, blank=True, default='')
    dob = models.DateField(blank=True, null=True, default=None)
    phonenumber = models.CharField(max_length=14, blank=True, default='')
    accountBalance = models.DecimalField(decimal_places=2, max_digits=12, default=Decimal('0.00'))
    accountNumber = models.CharField(max_length=10, default=generateAccountNumber)
    pin = models.CharField(max_length=4, blank=True)
    gender = models.CharField(max_length=1, default='U', choices=GENDER)

    def __str__(self):
        return f'{self.accountNumber} => NGN{self.accountBalance:,.2f}'

    @property
    def formatted_balance(self):
        return f'NGN{self.accountBalance:,.2f}'

class Transaction(models.Model):
    initiator = models.ForeignKey(Customer, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)
    amount = models.DecimalField(decimal_places=2, max_digits=12)
    status = models.CharField(max_length=10, choices=TRANSACTION_STATUS, default='PENDING')
    balance_after = models.DecimalField(decimal_places=2, max_digits=12)
    timestamp = models.DateTimeField(auto_now_add=True)
    # For Recipient
    recipient_account = models.CharField(max_length=10, blank=True, null=True)
    recipient_name = models.CharField(max_length=200, blank=True, null=True)
    reference = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self):
        return f'{self.transaction_type} - {self.amount} - {self.timestamp}'