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
def queue_control_dashboard(request):
    current_entry = QueueEntry.objects.filter(status='waiting').order_by('created_at').first()
    total_waiting = QueueEntry.objects.filter(status='waiting').count()
    served_today = QueueEntry.objects.filter(status='completed').count()

    context = {
        'current_entry': current_entry,
        'total_waiting': total_waiting,
        'served_today': served_today,
        'queue_paused': False,
    }
    return render(request, 'admin_queue_dashboard.html', context)


def queue_list(request):
    """Display all active queues that customers can join."""
    queues = Queue.objects.filter(is_active=True)
    context = {'queues': queues}
    return render(request, 'queue_list.html', context)

def join_queue(request, queue_id):
    """Allow a customer to join a queue by providing name, phone, and service."""
    queue = Queue.objects.get(id=queue_id)
    services = Service.objects.filter(is_active=True)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        service_id = request.POST.get('service')
        
        # Get or create customer
        customer, created = Customer.objects.get_or_create(
            email=f"{phone}@queue.local",  # Use phone as unique identifier
            defaults={'name': name, 'phone': phone}
        )
        
        # Get service
        service = Service.objects.get(id=service_id)
        
        # Get the next position in the queue
        last_entry = QueueEntry.objects.filter(queue=queue).order_by('-position').first()
        next_position = (last_entry.position + 1) if last_entry else 1
        
        # Create queue entry
        queue_entry = QueueEntry.objects.create(
            queue=queue,
            customer=customer,
            service=service,
            position=next_position,
            status='waiting'
        )
        
        # Redirect to a success page or dashboard
        return render(request, 'queue_join_success.html', {
            'queue_entry': queue_entry,
            'queue': queue,
            'customer': customer,
            'service': service
        })
    
    context = {'queue': queue, 'services': services}
    return render(request, 'join_queue.html', context)

