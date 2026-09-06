from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import BespokeRequestForm
from orders.models import Order, OrderNote


def bespoke_request_view(request):
    if request.method == 'POST':
        form = BespokeRequestForm(request.POST)
        if form.is_valid():
            bespoke_req = form.save()

            order = Order.objects.create(
                order_type='bespoke',
                bespoke_request=bespoke_req,
                customer_name=bespoke_req.name,
                customer_email=bespoke_req.email,
                phone_number=bespoke_req.phone,
                status='pending'
            )

            OrderNote.objects.create(
                order=order,
                note_type='system',
                content=f"Bespoke request received for: {bespoke_req.item_type}."
            )

            messages.success(request, 'Your bespoke request has been successfully submitted and added to our order queue! We will be in touch soon.')
            return redirect('home')
    else:
        form = BespokeRequestForm()

    return render(request, 'bespoke/bespoke_form.html', {'form': form})
