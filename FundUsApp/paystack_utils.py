import os

import requests
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY', '')
BASE_URL = os.getenv('PAYSTACK_API_BASE_URL')


def get_headers():
    return {
        'Authorization': f'Bearer {SECRET_KEY}',
        'Content-Type': 'application/json',
    }


def initializePayment(email, amount):
    """Initialize a Paystack transaction for a deposit."""
    data = {
        'email': email,
        'amount': int(amount),
        'callback_url': os.getenv('PAYSTACK_CALLBACK_URL', 'http://127.0.0.1:8000/callback/'),
    }

    try:
        response = requests.post(
            f'{BASE_URL}/transaction/initialize',
            json=data,
            headers=get_headers(),
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return payload
    except requests.RequestException as exc:
        return {'status': False, 'message': str(exc)}


def verifyPayment(reference: str):
    """Verify a Paystack transaction using its reference."""
    try:
        response = requests.get(
            f'{BASE_URL}/transaction/verify/{reference}',
            headers=get_headers(),
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get('status'):
            return {'status': True, 'message': 'Verification successful', 'data': payload}

        return {'status': False, 'message': payload.get('message', 'Payment not successful'), 'data': payload}
    except requests.RequestException as exc:
        return {'status': False, 'message': str(exc), 'data': None}
