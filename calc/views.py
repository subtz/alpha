from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import Queue, Customer, Service, QueueEntry

# Home view - renders the home.html template
def home(request):
    return render(request, 'calc/home.html')  # Pass the request to home.html and render it

# Register view
def register(request):
    if request.method == 'POST':  # When the form is submitted
        form = UserCreationForm(request.POST)  # Bind data to the form
        if form.is_valid():  # Check if the form data is valid
            user = form.save()  # Save the user to the database
            login(request, user)  # Log the user in automatically
            return redirect('dashboard')  # Redirect to dashboard after successful registration
    else:
        form = UserCreationForm()  # Create a blank form for GET request
    return render(request, 'calc/register.html', {'form': form})  # Render the register form in the template

# Login view
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')  # or another view like 'home'
        else:
            return render(request, 'calc/login.html', {'error': 'Invalid credentials'})
    return render(request, 'calc/login.html')

# Dashboard view - protected by login_required to ensure only authenticated users can access it
@login_required
def dashboard(request):
    return render(request, 'dashboard.html')  # Render the dashboard template

# Base view
def base(request):
    return render(request, 'calc/base.html')

# Index view
def index(request):
    return render(request, 'calc/home.html')

# Smart Queue views

@staff_member_required
def queue_control_dashboard(request, queue_id=None):
    queue = Queue.objects.get(id=queue_id) if queue_id else Queue.objects.first()
    current_entry = QueueEntry.objects.filter(queue=queue, status="waiting").order_by("created_at").first() if queue else None
    waiting_list = QueueEntry.objects.filter(queue=queue, status="waiting").order_by("created_at") if queue else QueueEntry.objects.none()
    total_waiting = waiting_list.count()
    served_today = QueueEntry.objects.filter(queue=queue, status="completed").count() if queue else 0

    context = {
        "queue": queue,
        "current_entry": current_entry,
        "waiting_list": waiting_list,
        "total_waiting": total_waiting,
        "served_today": served_today,
        "queue_paused": queue.is_paused if queue else False,
    }
    return render(request, "admin_queue_dashboard.html", context)


def queue_display(request):
    queue = Queue.objects.filter(is_active=True).first()
    now_serving = QueueEntry.objects.filter(queue=queue, status="serving").order_by("created_at").first() if queue else None
    next_ticket = QueueEntry.objects.filter(queue=queue, status="waiting").order_by("created_at").first() if queue else None
    total_waiting = QueueEntry.objects.filter(queue=queue, status="waiting").count() if queue else 0
    queue_status = "Paused" if queue and queue.is_paused else "Active" if queue else "No Active Queue"

    context = {
        "queue": queue,
        "now_serving": now_serving,
        "next_ticket": next_ticket,
        "total_waiting": total_waiting,
        "queue_status": queue_status,
    }
    return render(request, "display.html", context)


def queue_list(request):
    """Display all active queues that customers can join."""
    queues = Queue.objects.all()
    context = {'queues': queues}
    return render(request, 'queue_list.html', context)

def join_queue(request, queue_id):
    """Allow a customer to join a queue and show a success page with ticket info."""
    queue = Queue.objects.get(id=queue_id)
    services = Service.objects.filter(is_active=True)

    if request.method == 'POST':
        service_id = request.POST.get('service')
        service = Service.objects.get(id=service_id)

        if request.user.is_authenticated and request.user.email:
            customer, created = Customer.objects.get_or_create(
                email=request.user.email,
                defaults={
                    'name': request.user.get_full_name() or request.user.username,
                    'phone': ''
                }
            )
        else:
            name = request.POST.get('name')
            phone = request.POST.get('phone')
            customer, created = Customer.objects.get_or_create(
                email=f"{phone}@queue.local",
                defaults={'name': name, 'phone': phone}
            )

        last_entry = QueueEntry.objects.filter(queue=queue).order_by('-position').first()
        next_position = (last_entry.position + 1) if last_entry else 1

        entry = QueueEntry.objects.create(
            queue=queue,
            customer=customer,
            service=service,
            position=next_position,
            status='waiting'
        )

        position = QueueEntry.objects.filter(queue=queue, status='waiting').order_by('created_at').count()

        return render(request, 'queue_join_success.html', {
            'entry': entry,
            'position': position,
            'queue': queue,
        })

    context = {'queue': queue, 'services': services}
    return render(request, 'join_queue.html', context)


@staff_member_required
def serve_current(request):
    current = QueueEntry.objects.filter(status="waiting").order_by("created_at").first()
    if current:
        current.status = "completed"
        current.save()
    return redirect("queue_control_dashboard")


@staff_member_required
def skip_current(request):
    current = QueueEntry.objects.filter(status="waiting").order_by("created_at").first()
    if current:
        current.status = "skipped"
        current.save()
    return redirect("queue_control_dashboard")


@staff_member_required
def toggle_queue_pause(request, queue_id):
    queue = Queue.objects.get(id=queue_id)
    queue.is_paused = not queue.is_paused
    queue.save()
    return redirect("queue_control_dashboard", queue_id=queue.id)

