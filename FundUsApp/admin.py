from django.contrib import admin
from .models import Customer, Transaction


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('initiator', 'transaction_type', 'amount', 'status', 'balance_after', 'timestamp')
    list_filter = ('transaction_type', 'status')
    search_fields = ('initiator__user__username', 'recipient_name', 'recipient_account')

    def save_model(self, request, obj, form, change):
        customer = obj.initiator
        if not customer:
            super().save_model(request, obj, form, change)
            return

        previous = Transaction.objects.filter(pk=obj.pk).first() if change else None

        if previous and previous.status == 'SUCCESS':
            if previous.transaction_type == 'DEPOSIT':
                customer.accountBalance -= previous.amount
            elif previous.transaction_type in ('WITHDRAWAL', 'TRANSFER'):
                customer.accountBalance += previous.amount

        if obj.status == 'SUCCESS':
            if obj.transaction_type == 'DEPOSIT':
                customer.accountBalance += obj.amount
            elif obj.transaction_type in ('WITHDRAWAL', 'TRANSFER'):
                customer.accountBalance -= obj.amount

        customer.save(update_fields=['accountBalance'])
        obj.balance_after = customer.accountBalance
        super().save_model(request, obj, form, change)


admin.site.register(Customer)
admin.site.register(Transaction, TransactionAdmin)