import os

import requests
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY', '')
BASE_URL = 'https://api.paystack.co'


def get_headers():
    return {
        'Authorization': f'Bearer {SECRET_KEY}',
        'Content-Type': 'application/json',
    }


def createPaymentPage():
    data = {
        'name': 'FundUs',
        'amount': 20000000,
        'description': 'FundUs supports secure deposits and transfers for your account.',
    }
    try:
        response = requests.post(
            f'{BASE_URL}/page',
            json=data,
            headers=get_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {'error': str(exc)}


def initializePayment(email, amount):
    data = {
        'email': email,
        'amount': amount,
        'callback_url': 'http://127.0.0.1:8000/callback/',
    }
    try:
        response = requests.post(
            f'{BASE_URL}/transaction/initialize',
            json=data,
            headers=get_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {'error': str(exc)}


def verifyPayment(reference: str):
    try:
        response = requests.get(
            f'{BASE_URL}/transaction/verify/{reference}',
            headers=get_headers(),
            timeout=30,
        )
        response.raise_for_status()
        resp_data = response.json()

        if resp_data.get('status'):
            amount_paid = resp_data['data']['amount']
            return {
                'status': True,
                'message': f'Payment successful. Amount paid: NGN{(amount_paid / 100):,.2f}',
                'data': resp_data,
            }

        return {'status': False, 'data': resp_data}
    except requests.RequestException as exc:
        return {'error': str(exc)}


if __name__ == '__main__':
    print('createPaymentPage ->', createPaymentPage())
    print('initializePayment ->', initializePayment('marvelousobasola4@gmail.com', 4500 * 100))
    print('verifyPayment ->', verifyPayment('00gr14wmqz'))
