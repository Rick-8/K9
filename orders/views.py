from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from .models import Order, OrderNote


@staff_member_required
def order_dashboard(request):
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    show_closed = request.GET.get('show_closed') == '1'

    orders = Order.objects.all()

    if search_query:
        # Search is global: always search every order, including Sent and
        # Cancelled, even when the closed-orders switch is off.
        orders = orders.filter(
            Q(reference_number__icontains=search_query)
            | Q(customer_name__icontains=search_query)
            | Q(customer_email__icontains=search_query)
            | Q(phone_number__icontains=search_query)
            | Q(tracking_number__icontains=search_query)
        )

        # Only honour a genuinely specific status choice during a search.
        # Ignore the default/stale "active" value so closed matches are not
        # accidentally hidden.
        if status_filter in {'pending', 'processing', 'sent', 'cancelled'}:
            orders = orders.filter(status=status_filter)
    else:
        # Normal dashboard browsing: show active work only unless staff
        # deliberately enable the closed-orders switch.
        if show_closed:
            if status_filter in {'pending', 'processing', 'sent', 'cancelled'}:
                orders = orders.filter(status=status_filter)
        else:
            if status_filter in {'pending', 'processing'}:
                orders = orders.filter(status=status_filter)
            else:
                orders = orders.filter(status__in=['pending', 'processing'])

    orders = orders.order_by('-created_at')

    counts = Order.objects.aggregate(
        pending=Count('id', filter=Q(status='pending')),
        processing=Count('id', filter=Q(status='processing')),
        sent=Count('id', filter=Q(status='sent')),
        cancelled=Count('id', filter=Q(status='cancelled')),
    )

    context = {
        'orders': orders,
        'search_query': search_query,
        'status_filter': status_filter,
        'show_closed': show_closed,
        'status_counts': counts,
    }
    return render(request, 'orders/dashboard.html', context)


@staff_member_required
def order_detail(request, reference_number):
    order = get_object_or_404(Order, reference_number=reference_number)

    if request.method == 'POST':
        if 'mark_complete' in request.POST:
            old_status = order.status
            order.status = 'sent'
            order.save()
            OrderNote.objects.create(
                order=order, note_type='system', author=request.user,
                content=f"Status changed from {old_status} to sent via Quick-Action button."
            )
            messages.success(request, "Order timestamped and marked as Sent.")
            return redirect('order_detail', reference_number=order.reference_number)

        elif 'update_order' in request.POST:
            old_status = order.status
            new_status = request.POST.get('status')
            cancel_reason = request.POST.get('cancel_reason', '').strip()

            valid_statuses = {choice[0] for choice in Order.STATUS_CHOICES}
            if new_status not in valid_statuses:
                messages.error(request, "Invalid order status selected.")
                return redirect('order_detail', reference_number=order.reference_number)

            is_new_cancellation = (
                new_status == 'cancelled' and old_status != 'cancelled'
            )

            # Server-side protection: JavaScript can be bypassed, so Django also
            # requires a cancellation reason before changing the status.
            if is_new_cancellation and not cancel_reason:
                messages.error(request, "Please provide a reason for cancelling the order.")
                return redirect('order_detail', reference_number=order.reference_number)

            with transaction.atomic():
                # Write the cancellation reason into the comms/staff log first.
                if is_new_cancellation:
                    OrderNote.objects.create(
                        order=order,
                        note_type='system',
                        author=request.user,
                        content=f"Order cancelled. Reason: {cancel_reason}"
                    )

                order.status = new_status
                order.customer_name = request.POST.get('customer_name')
                order.customer_email = request.POST.get('customer_email')
                order.phone_number = request.POST.get('phone_number')
                order.shipping_address = request.POST.get('shipping_address')
                order.tracking_number = request.POST.get('tracking_number')

                total_val = request.POST.get('order_total')
                if total_val:
                    order.order_total = total_val

                order.save()

                # For normal updates/status changes, add the usual system log.
                # A cancellation already has its own clearer comms entry above.
                if not is_new_cancellation:
                    if old_status != new_status:
                        note_content = f"Status changed from {old_status} to {new_status}."
                    else:
                        note_content = "Order details updated."

                    OrderNote.objects.create(
                        order=order,
                        note_type='system',
                        author=request.user,
                        content=note_content
                    )

            if is_new_cancellation:
                messages.success(request, "Cancellation reason logged and order cancelled.")
            else:
                messages.success(request, "Order details updated successfully.")

            return redirect('order_detail', reference_number=order.reference_number)

        elif 'add_note' in request.POST:
            content = request.POST.get('note_content')
            note_type = request.POST.get('note_type', 'internal')
            if content:
                OrderNote.objects.create(
                    order=order, note_type=note_type, content=content, author=request.user
                )
                messages.success(request, "Note added successfully.")
            return redirect('order_detail', reference_number=order.reference_number)

    return render(request, 'orders/order_detail.html', {'order': order})
