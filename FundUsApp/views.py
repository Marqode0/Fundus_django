from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Customer, Transaction
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.utils import IntegrityError
from django.contrib.auth import authenticate, login as loginuser, logout as logoutuser
from decimal import Decimal, InvalidOperation
from django.db.models import Q, Sum
from django.http import JsonResponse
import uuid

from .paystack_utils import initializePayment as paystack_initialize
from .paystack_utils import verifyPayment as paystack_verify

def homepage(request):
    return render(request, 'index.html')

def dashboard(request):
    request
    if not request.user.is_authenticated:
        return redirect('LoginPage')
    # block admin/superusers — only real customers allowed
    if request.user.is_superuser or request.user.is_staff:
        logoutuser(request)
        return redirect('LoginPage')
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        logoutuser(request)
        return redirect('LoginPage')
    transactions = Transaction.objects.filter(
        initiator=customer
    ).order_by('-timestamp')[:10]
    return render(request, 'dashboard.html', {
        'customer': customer,
        'transactions': transactions,
    })

def loginPage(request):
    if request.user.is_authenticated and not request.user.is_superuser:
        return redirect('DashboardPage')
    return render(request, 'login.html')

def signupPage(request):
    if request.user.is_authenticated and not request.user.is_superuser:
        return redirect('DashboardPage')
    return render(request, 'signup.html')

def contactpage(request):
    call = '''
    <form>
    <input type="email" value="Enter Your email">
    </form>'''
    return HttpResponse(call)

def aboutpage(request):
    about = '<h4>This is about FundUsApp</h4>'
    return HttpResponse(about)

def contactPage(request):
    customer = Customer.objects.filter(id=1).first()
    return render(request, 'contact.html', {
        'customer': customer,
    })

def ProcessSignUp(request):
    if request.method == "POST":
        data = request.POST
        email = data.get('email', '').strip()
        password = data.get('password', '')
        pin = data.get('pin', '').strip()

        if not email or len(email) < 4:
            messages.error(request, "Email Required")
            return redirect('SignUpPage')

        if not password or len(password) < 6:
            messages.error(request, "Password is too short")
            return redirect('SignUpPage')

        if not pin or len(pin) != 4 or not pin.isdigit():
            messages.error(request, "PIN must be exactly 4 digits")
            return redirect('SignUpPage')

        full_name = data.get('full_name', '').strip()
        first_name = ''
        last_name = ''
        if full_name:
            parts = full_name.split()
            first_name = parts[0]
            last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        try:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            user.save()
            Customer.objects.create(user=user, pin=pin)
            messages.success(request, "Account created! Please log in.")
            return redirect('LoginPage')
        except IntegrityError:
            messages.error(request, "An account with this email already exists.")
            return redirect('SignUpPage')

    return redirect('SignUpPage')

def ProcessLogin(request):
    if request.method == "POST":
        data = request.POST
        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not email or len(email) < 2:
            messages.error(request, "Email is required")
            return redirect('LoginPage')

        if not password:
            messages.error(request, "Password is required")
            return redirect('LoginPage')

        user = authenticate(request, username=email, password=password)

        if not user:
            messages.error(request, "Invalid email or password")
            return redirect('LoginPage')

        # block admin from using the app login
        if user.is_superuser or user.is_staff:
            messages.error(request, "Invalid email or password")
            return redirect('LoginPage')

        # check customer profile exists
        customer = Customer.objects.filter(user=user).first()
        if not customer:
            messages.error(request, "No account found. Please sign up.")
            return redirect('SignUpPage')

        # Fix: Ensure accountBalance is not None
        if customer.accountBalance is None:
            customer.accountBalance = Decimal('0.00')
            customer.save()

        loginuser(request, user)
        messages.success(request, f"Welcome back, {user.first_name or user.username}!")
        return redirect('DashboardPage')

    return redirect('LoginPage')

def logoutPage(request):
    if request.method == "POST":
        logoutuser(request)
        return redirect('HomePage')
    return redirect('HomePage')

def transferPage(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')
    return render(request, 'transfer.html', {'customer': customer})

def depositPage(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')

    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')

    if request.method == 'POST':
        amount_raw = request.POST.get('amount', '').strip()

        try:
            amount = Decimal(str(amount_raw))
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError, InvalidOperation):
            messages.error(request, 'Enter a valid amount')
            return redirect('DepositPage')

        customer.accountBalance += amount
        customer.save()

        reference = f"DEP-{customer.accountNumber}-{uuid.uuid4().hex[:10].upper()}"
        transaction = Transaction.objects.create(
            initiator=customer,
            reference=reference,
            transaction_type='DEPOSIT',
            amount=amount,
            status='SUCCESS',
            balance_after=customer.accountBalance,
            recipient_account=customer.accountNumber,
            recipient_name=customer.user.get_full_name() or customer.user.username,
        )

        return render(request, 'receipt.html', {
            'customer': customer,
            'transaction': transaction,
            'bank': 'FundUs MFB',
            'narration': 'Deposit to FundUs account',
        })

    return render(request, 'deposit.html', {'customer': customer})

def processTransfer(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')

    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')

    if request.method == "POST":
        data = request.POST
        recipient_account = data.get('recipient_account', '').strip()
        bank = data.get('bank', '').strip()
        recipient_name = data.get('recipient_name', '').strip()
        amount = data.get('amount', '').strip()
        narration = data.get('narration', '').strip()
        pin = data.get('pin', '').strip()

        # Validate fields
        if not recipient_account or len(recipient_account) != 10:
            messages.error(request, "Enter a valid 10-digit account number")
            return redirect('TransferPage')

        if not bank:
            messages.error(request, "Please select a bank")
            return redirect('TransferPage')

        if not recipient_name:
            messages.error(request, "Recipient name is required")
            return redirect('TransferPage')

        try:
            amount = Decimal(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError, InvalidOperation):
            messages.error(request, "Enter a valid amount")
            return redirect('TransferPage')

        if not pin or len(pin) != 4:
            messages.error(request, "Enter your 4-digit PIN")
            return redirect('TransferPage')

        # Check PIN
        if customer.pin != pin:
            messages.error(request, "Incorrect PIN. Please try again.")
            return redirect('TransferPage')

        # Check balance
        if customer.accountBalance < amount:
            messages.error(request, "Insufficient balance")
            return redirect('TransferPage')
        
        # Reject if recipient is not a FundUs Customer
        recipient_customer = Customer.objects.filter(accountNumber=recipient_account).first()
        if not recipient_customer:
            messages.error(request, "This Account Number is not registered on Fundus")
            return redirect('TransferPage')
        
        # prevent sending to yourself
        if recipient_account == customer.accountNumber:
            messages.error(request, "You cannot transfer to your own account")
            return redirect('TransferPage')
        
        # Deduct balance
        customer.accountBalance -= amount
        customer.save()

        recipient_customer.accountBalance += amount
        recipient_customer.save()

        Transaction.objects.create(
            initiator=recipient_customer,
            transaction_type='DEPOSIT',
            amount=amount,
            status='SUCCESS',
            balance_after=recipient_customer.accountBalance,
            recipient_account=customer.accountNumber,
            recipient_name=customer.user.username,
        )

        # Create transaction record
        transaction = Transaction.objects.create(
            initiator=customer,
            transaction_type='TRANSFER',
            amount=amount,
            status='SUCCESS',
            balance_after=customer.accountBalance,
            recipient_account=recipient_account,
            recipient_name=recipient_name,
        )

        return render(request, 'receipt.html', {
            'customer': customer,
            'transaction': transaction,
            'bank': bank,
            'narration': narration,
        })

    return redirect('TransferPage')

def verifyAccount(request):
    account_number = request.GET.get('account_number', '').strip()
    if len(account_number) != 10:
        return JsonResponse({'valid': False})
    
    recipient = Customer.objects.filter(accountNumber=account_number).first()
    if recipient:
        return JsonResponse({
            'valid': True,
            'name': recipient.user.get_full_name() or recipient.user.username,
        })
    return JsonResponse({'valid': False})

def initialize_paystack_deposit(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')

    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')

    if request.method != 'POST':
        return redirect('DepositPage')

    amount_raw = request.POST.get('amount', '').strip()
    try:
        amount = Decimal(str(amount_raw))
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError, InvalidOperation):
        messages.error(request, 'Enter a valid amount')
        return redirect('DepositPage')

    email = request.user.email or request.user.username
    amount_kobo = int((amount * Decimal('100')).quantize(Decimal('1')))
    result = paystack_initialize(email, amount_kobo)

    if not result.get('status') or not result.get('data', {}).get('authorization_url'):
        messages.error(request, result.get('message') or 'Unable to start Paystack payment right now.')
        return redirect('DepositPage')

    reference = result['data'].get('reference')
    Transaction.objects.create(
        initiator=customer,
        transaction_type='DEPOSIT',
        amount=amount,
        status='PENDING',
        balance_after=customer.accountBalance,
        reference=reference,
        recipient_account=customer.accountNumber,
        recipient_name=customer.user.get_full_name() or customer.user.username,
    )

    return redirect(result['data']['authorization_url'])


def paystack_callback(request):
    reference = request.GET.get('reference') or request.GET.get('trxref')

    if not reference:
        messages.error(request, 'Payment reference is missing.')
        return redirect('LoginPage')

    # Find transaction by reference — no need for request.user here
    transaction = Transaction.objects.filter(reference=reference).first()
    if not transaction:
        messages.error(request, 'Transaction not found.')
        return redirect('LoginPage')

    # Get customer from the transaction itself
    customer = transaction.initiator

    # Check if already processed
    if transaction.status == 'SUCCESS':
        messages.error(request, 'This transaction has already been processed.')
        if request.user.is_authenticated:
            return redirect('DashboardPage')
        return redirect('LoginPage')

    # Verify with Paystack API
    result = paystack_verify(reference)

    if not result.get('status'):
        transaction.status = 'FAILED'
        transaction.save()
        messages.error(request, result.get('message') or 'Payment verification failed.')
        return redirect('LoginPage')

    # Get payment data from Paystack response
    payment_data = result.get('data', {}).get('data', {})
    paystack_status = payment_data.get('status', '')

    if paystack_status != 'success':
        transaction.status = 'FAILED'
        transaction.save()
        messages.error(request, f'Payment was not successful. Status: {paystack_status}')
        return redirect('LoginPage')

    # Get actual amount paid (Paystack returns kobo)
    amount_paid = Decimal(payment_data.get('amount', 0)) / Decimal('100')

    # Credit customer balance
    customer.accountBalance += amount_paid
    customer.save()

    # Update transaction
    transaction.amount = amount_paid
    transaction.status = 'SUCCESS'
    transaction.balance_after = customer.accountBalance
    transaction.save()

    # Log the customer back in automatically
    loginuser(request, customer.user)

    messages.success(request, f'Deposit of NGN{amount_paid:,.2f} successful!')
    return render(request, 'receipt.html', {
        'customer': customer,
        'transaction': transaction,
        'bank': 'Paystack',
        'narration': 'Paystack deposit',
    })


def processDeposit(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')

    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')

    if request.method == 'POST':
        data = request.POST
        amount = data.get('amount', '').strip()
        pin = data.get('pin', '').strip()
        narration = data.get('narration', '').strip()

        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, 'Enter a valid amount')
            return redirect('DepositPage')

        if not pin or len(pin) != 4:
            messages.error(request, 'Enter your 4-digit PIN')
            return redirect('DepositPage')

        if customer.pin != pin:
            messages.error(request, 'Incorrect PIN. Please try again.')
            return redirect('DepositPage')

        customer.accountBalance += amount
        customer.save()

        transaction = Transaction.objects.create(
            initiator=customer,
            transaction_type='DEPOSIT',
            amount=amount,
            status='SUCCESS',
            balance_after=customer.accountBalance,
            recipient_account=customer.accountNumber,
            recipient_name=customer.user.get_full_name() or customer.user.username,
        )

        return render(request, 'receipt.html', {
            'customer': customer,
            'transaction': transaction,
            'bank': 'FundUs MFB',
            'narration': narration or 'Deposit to FundUs account',
        })

    return redirect('DepositPage')

def processWithdrawal(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')

    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')

    if request.method == 'POST':
        data = request.POST
        bank = data.get('bank', '').strip()
        account_number = data.get('account_number', '').strip()
        amount = data.get('amount', '').strip()
        pin = data.get('pin', '').strip()
        narration = data.get('narration', '').strip()

        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, 'Enter a valid amount')
            return redirect('DashboardPage')

        if not bank:
            messages.error(request, 'Please select your bank')
            return redirect('DashboardPage')

        if not account_number or len(account_number) < 10:
            messages.error(request, 'Enter a valid bank account number')
            return redirect('DashboardPage')

        if not pin or len(pin) != 4:
            messages.error(request, 'Enter your 4-digit PIN')
            return redirect('DashboardPage')

        if customer.pin != pin:
            messages.error(request, 'Incorrect PIN. Please try again.')
            return redirect('DashboardPage')

        if customer.accountBalance < amount:
            messages.error(request, 'Insufficient balance')
            return redirect('DashboardPage')

        customer.accountBalance -= amount
        customer.save()

        transaction = Transaction.objects.create(
            initiator=customer,
            transaction_type='WITHDRAWAL',
            amount=amount,
            status='SUCCESS',
            balance_after=customer.accountBalance,
            recipient_account=account_number,
            recipient_name=bank,
        )

        return render(request, 'receipt.html', {
            'customer': customer,
            'transaction': transaction,
            'bank': bank,
            'narration': narration or 'Withdrawal from FundUs account',
        })

    return redirect('DashboardPage')

def profilePage(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')
    return render(request, 'profile.html', {'customer': customer})

def updateInfo(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        dob = request.POST.get('dob', '').strip()
        gender = request.POST.get('gender', 'U').strip()

        if not first_name or not last_name:
            messages.error(request, "First and last name are required")
            return redirect('ProfilePage')

        # update User model
        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.save()

        # update Customer model
        customer.phonenumber = phone
        customer.gender = gender
        if dob:
            customer.dob = dob
        customer.save()

        messages.success(request, "Profile updated successfully!")
        return redirect('ProfilePage')

    return redirect('ProfilePage')

def updatePassword(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')

    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        # verify current password
        user = authenticate(request, username=request.user.username, password=current_password)
        if not user:
            messages.error(request, "Current password is incorrect")
            return redirect('ProfilePage')

        if len(new_password) < 6:
            messages.error(request, "New password must be at least 6 characters")
            return redirect('ProfilePage')

        if new_password != confirm_password:
            messages.error(request, "New passwords do not match")
            return redirect('ProfilePage')

        request.user.set_password(new_password)
        request.user.save()
        # log user back in after password change
        loginuser(request, request.user)
        messages.success(request, "Password updated successfully!")
        return redirect('ProfilePage')

    return redirect('ProfilePage')

def updatePin(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')

    if request.method == 'POST':
        current_pin = request.POST.get('current_pin', '').strip()
        new_pin = request.POST.get('new_pin', '').strip()
        confirm_pin = request.POST.get('confirm_pin', '').strip()

        # if customer already has a pin, verify it
        if customer.pin:
            if current_pin != customer.pin:
                messages.error(request, "Current PIN is incorrect")
                return redirect('ProfilePage')

        if len(new_pin) != 4 or not new_pin.isdigit():
            messages.error(request, "PIN must be exactly 4 digits")
            return redirect('ProfilePage')

        if new_pin != confirm_pin:
            messages.error(request, "PINs do not match")
            return redirect('ProfilePage')

        customer.pin = new_pin
        customer.save()
        messages.success(request, "Transaction PIN updated successfully!")
        return redirect('ProfilePage')

    return redirect('ProfilePage')

def historyPage(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')

    # base queryset
    all_tx = Transaction.objects.filter(initiator=customer).order_by('-timestamp')

    # search filter
    search = request.GET.get('search', '').strip()
    if search:
        all_tx = all_tx.filter(
            Q(transaction_type__icontains=search) |
            Q(recipient_name__icontains=search) |
            Q(recipient_account__icontains=search)
        )

    # date filter
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    if date_from:
        all_tx = all_tx.filter(timestamp__date__gte=date_from)
    if date_to:
        all_tx = all_tx.filter(timestamp__date__lte=date_to)

    # split by type
    deposit_tx = all_tx.filter(transaction_type='DEPOSIT')
    transfer_tx = all_tx.filter(transaction_type='TRANSFER')
    withdrawal_tx = all_tx.filter(transaction_type='WITHDRAWAL')

    # summary totals
    total_deposits = deposit_tx.aggregate(Sum('amount'))['amount__sum'] or 0
    total_transfers = transfer_tx.aggregate(Sum('amount'))['amount__sum'] or 0

    return render(request, 'history.html', {
        'customer': customer,
        'all_transactions': all_tx,
        'deposit_transactions': deposit_tx,
        'transfer_transactions': transfer_tx,
        'withdrawal_transactions': withdrawal_tx,
        'total_deposits': total_deposits,
        'total_transfers': total_transfers,
        'total_count': all_tx.count(),
    })

def withdrawPage(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')
    return render(request, 'withdraw.html', {'customer': customer})


def processWithdraw(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')

    if request.method == "POST":
        data = request.POST
        bank = data.get('bank', '').strip()
        bank_account = data.get('bank_account', '').strip()
        account_name = data.get('account_name', '').strip()
        amount = data.get('amount', '').strip()
        pin = data.get('pin', '').strip()

        if not bank:
            messages.error(request, "Please select your bank")
            return redirect('WithdrawPage')

        if not bank_account or len(bank_account) != 10:
            messages.error(request, "Enter a valid 10-digit account number")
            return redirect('WithdrawPage')

        if not account_name:
            messages.error(request, "Account name is required")
            return redirect('WithdrawPage')

        try:
            amount = Decimal(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError, InvalidOperation):
            messages.error(request, "Enter a valid amount")
            return redirect('WithdrawPage')

        if not pin or len(pin) != 4:
            messages.error(request, "Enter your 4-digit PIN")
            return redirect('WithdrawPage')

        if customer.pin != pin:
            messages.error(request, "Incorrect PIN. Please try again.")
            return redirect('WithdrawPage')

        if customer.accountBalance < amount:
            messages.error(request, "Insufficient balance")
            return redirect('WithdrawPage')

        customer.accountBalance -= amount
        customer.save()

        transaction = Transaction.objects.create(
            initiator=customer,
            transaction_type='WITHDRAWAL',
            amount=amount,
            status='SUCCESS',
            balance_after=customer.accountBalance,
            recipient_account=bank_account,
            recipient_name=f"{account_name} ({bank})",
        )

        return render(request, 'receipt.html', {
            'customer': customer,
            'transaction': transaction,
            'bank': bank,
            'narration': 'Withdrawal to bank account',
        })

    return redirect('WithdrawPage')


def billsPage(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')
    return render(request, 'paybills.html', {'customer': customer})


def processBill(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')

    if request.method == "POST":
        data = request.POST
        bill_type = data.get('bill_type', '').strip()
        meter_number = data.get('meter_number', '').strip()
        provider = data.get('provider', '').strip()
        amount = data.get('amount', '').strip()
        pin = data.get('pin', '').strip()

        if not bill_type or not provider:
            messages.error(request, "Please select bill type and provider")
            return redirect('BillsPage')

        if not meter_number:
            messages.error(request, "Meter/Smartcard number is required")
            return redirect('BillsPage')

        try:
            amount = Decimal(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError, InvalidOperation):
            messages.error(request, "Enter a valid amount")
            return redirect('BillsPage')

        if not pin or len(pin) != 4:
            messages.error(request, "Enter your 4-digit PIN")
            return redirect('BillsPage')

        if customer.pin != pin:
            messages.error(request, "Incorrect PIN. Please try again.")
            return redirect('BillsPage')

        if customer.accountBalance < amount:
            messages.error(request, "Insufficient balance")
            return redirect('BillsPage')

        customer.accountBalance -= amount
        customer.save()

        transaction = Transaction.objects.create(
            initiator=customer,
            transaction_type='WITHDRAWAL',
            amount=amount,
            status='SUCCESS',
            balance_after=customer.accountBalance,
            recipient_account=meter_number,
            recipient_name=f"{provider} ({bill_type})",
        )

        return render(request, 'receipt.html', {
            'customer': customer,
            'transaction': transaction,
            'bank': provider,
            'narration': f"{bill_type} bill payment",
        })

    return redirect('BillsPage')


def airtimePage(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')
    return render(request, 'airtime.html', {'customer': customer})


def processAirtime(request):
    if not request.user.is_authenticated:
        return redirect('LoginPage')
    customer = Customer.objects.filter(user=request.user).first()
    if not customer:
        return redirect('LoginPage')

    if request.method == "POST":
        data = request.POST
        network = data.get('network', '').strip()
        phone_number = data.get('phone_number', '').strip()
        amount = data.get('amount', '').strip()
        pin = data.get('pin', '').strip()

        if not network:
            messages.error(request, "Please select a network")
            return redirect('AirtimePage')

        if not phone_number or len(phone_number) != 11:
            messages.error(request, "Enter a valid 11-digit phone number")
            return redirect('AirtimePage')

        try:
            amount = Decimal(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError, InvalidOperation):
            messages.error(request, "Enter a valid amount")
            return redirect('AirtimePage')

        if not pin or len(pin) != 4:
            messages.error(request, "Enter your 4-digit PIN")
            return redirect('AirtimePage')

        if customer.pin != pin:
            messages.error(request, "Incorrect PIN. Please try again.")
            return redirect('AirtimePage')

        if customer.accountBalance < amount:
            messages.error(request, "Insufficient balance")
            return redirect('AirtimePage')

        customer.accountBalance -= amount
        customer.save()

        transaction = Transaction.objects.create(
            initiator=customer,
            transaction_type='WITHDRAWAL',
            amount=amount,
            status='SUCCESS',
            balance_after=customer.accountBalance,
            recipient_account=phone_number,
            recipient_name=f"{network} Airtime",
        )

        return render(request, 'receipt.html', {
            'customer': customer,
            'transaction': transaction,
            'bank': network,
            'narration': f"Airtime top-up for {phone_number}",
        })

    return redirect('AirtimePage')