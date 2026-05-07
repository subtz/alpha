from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from django import forms
from .models import Queue, Customer, Service, QueueEntry, ValidStudent, StudentProfile

# Custom registration form with registration_number field
class StudentRegistrationForm(UserCreationForm):
    registration_number = forms.CharField(
        max_length=50,
        required=True,
        help_text="Enter your student registration number",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., STU001'})
    )

    class Meta:
        from django.contrib.auth.models import User
        model = User
        fields = ('registration_number', 'username', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})

# Home view - renders the home.html template
def home(request):
    return render(request, 'calc/home.html')  # Pass the request to home.html and render it

# Register view
def register(request):
    if request.method == 'POST':  # When the form is submitted
        form = StudentRegistrationForm(request.POST)  # Bind data to the form
        registration_number = request.POST.get('registration_number')
        
        # Validate that student is registered
        try:
            valid_student = ValidStudent.objects.get(registration_number=registration_number, is_active=True)
        except ValidStudent.DoesNotExist:
            # Return error if not a registered student
            form.add_error('registration_number', 'You are not a registered student')
            return render(request, 'calc/register.html', {'form': form, 'error': 'You are not a registered student'})
        
        if form.is_valid():  # Check if the form data is valid
            user = form.save()  # Save the user to the database
            # Create StudentProfile linking user to valid_student
            StudentProfile.objects.create(user=user, valid_student=valid_student)
            login(request, user)  # Log the user in automatically
            return redirect('dashboard')  # Redirect to dashboard after successful registration
    else:
        form = StudentRegistrationForm()  # Create a blank form for GET request
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
    today = timezone.localdate()
    queue = Queue.objects.get(id=queue_id) if queue_id else Queue.objects.first()
    current_entry = QueueEntry.objects.filter(queue=queue, status="waiting").order_by("created_at").first() if queue else None
    waiting_list = QueueEntry.objects.filter(queue=queue, status="waiting").order_by("created_at") if queue else QueueEntry.objects.none()
    total_waiting = waiting_list.count()
    served_today = QueueEntry.objects.filter(queue=queue, status="completed", completed_at__date=today).count() if queue else 0

    context = {
        "queue": queue,
        "current_entry": current_entry,
        "waiting_list": waiting_list,
        "total_waiting": total_waiting,
        "served_today": served_today,
        "queue_paused": queue.is_paused if queue else False,
    }
    return render(request, "admin_queue_dashboard.html", context)


@staff_member_required
def staff_reports(request):
    today = timezone.localdate()

    completed_today_qs = QueueEntry.objects.filter(status="completed", completed_at__date=today)
    total_served_today = completed_today_qs.count()
    active_waiting_count = QueueEntry.objects.filter(status="waiting").count()
    skipped_today = QueueEntry.objects.filter(status="skipped", created_at__date=today).count()
    total_tickets_today = QueueEntry.objects.filter(created_at__date=today).count()

    wait_deltas = []
    for entry in completed_today_qs:
        end_time = entry.served_at or entry.completed_at
        if end_time and entry.created_at:
            wait_deltas.append((end_time - entry.created_at).total_seconds() / 60.0)

    average_waiting_minutes = round(sum(wait_deltas) / len(wait_deltas), 1) if wait_deltas else 0.0

    created_hours = {hour: 0 for hour in range(24)}
    completed_hours = {hour: 0 for hour in range(24)}
    for entry in QueueEntry.objects.filter(created_at__date=today):
        hour = entry.created_at.astimezone(timezone.get_current_timezone()).hour
        created_hours[hour] += 1
    for entry in completed_today_qs:
        if entry.completed_at:
            hour = entry.completed_at.astimezone(timezone.get_current_timezone()).hour
            completed_hours[hour] += 1

    hourly_metrics = []
    for hour in range(24):
        hourly_metrics.append({
            "hour": f"{hour:02d}:00",
            "demand": created_hours.get(hour, 0),
            "throughput": completed_hours.get(hour, 0),
        })

    context = {
        "today": today,
        "total_served_today": total_served_today,
        "active_waiting_count": active_waiting_count,
        "average_waiting_minutes": average_waiting_minutes,
        "skipped_today": skipped_today,
        "total_tickets_today": total_tickets_today,
        "hourly_metrics": hourly_metrics,
    }
    return render(request, "staff_reports.html", context)


@staff_member_required
def export_reports_pdf(request):
    today = timezone.localdate()

    completed_today_qs = QueueEntry.objects.filter(status="completed", completed_at__date=today)
    total_served_today = completed_today_qs.count()
    active_waiting_count = QueueEntry.objects.filter(status="waiting").count()
    skipped_today = QueueEntry.objects.filter(status="skipped", created_at__date=today).count()
    total_tickets_today = QueueEntry.objects.filter(created_at__date=today).count()

    wait_deltas = []
    for entry in completed_today_qs:
        end_time = entry.served_at or entry.completed_at
        if end_time and entry.created_at:
            wait_deltas.append((end_time - entry.created_at).total_seconds() / 60.0)

    average_waiting_minutes = round(sum(wait_deltas) / len(wait_deltas), 1) if wait_deltas else 0.0

    created_hours = {hour: 0 for hour in range(24)}
    completed_hours = {hour: 0 for hour in range(24)}
    for entry in QueueEntry.objects.filter(created_at__date=today):
        hour = entry.created_at.astimezone(timezone.get_current_timezone()).hour
        created_hours[hour] += 1
    for entry in completed_today_qs:
        if entry.completed_at:
            hour = entry.completed_at.astimezone(timezone.get_current_timezone()).hour
            completed_hours[hour] += 1

    hourly_metrics = []
    for hour in range(24):
        hourly_metrics.append({
            "hour": f"{hour:02d}:00",
            "demand": created_hours.get(hour, 0),
            "throughput": completed_hours.get(hour, 0),
        })

    # Generate PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="queue_report_{today}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title = Paragraph("DUCE SmartCard Center Queue Report", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))

    # Report Date
    date_text = Paragraph(f"Report Date: {today}", styles['Normal'])
    elements.append(date_text)
    elements.append(Spacer(1, 12))

    # Summary Table
    summary_data = [
        ['Metric', 'Value'],
        ['Total Tickets Created Today', str(total_tickets_today)],
        ['Total Served Today', str(total_served_today)],
        ['Active Waiting Count', str(active_waiting_count)],
        ['Skipped Today', str(skipped_today)],
        ['Average Wait Time (minutes)', str(average_waiting_minutes)],
    ]
    summary_table = Table(summary_data)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 24))

    # Hourly Table
    hourly_data = [['Hour', 'Demand', 'Throughput']]
    for metric in hourly_metrics:
        hourly_data.append([metric['hour'], str(metric['demand']), str(metric['throughput'])])
    hourly_table = Table(hourly_data)
    hourly_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(hourly_table)

    doc.build(elements)
    return response


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
        now = timezone.now()
        current.status = "completed"
        current.served_at = now
        current.completed_at = now
        current.save()
    return redirect("queue_control_dashboard")


@staff_member_required
def skip_current(request):
    current = QueueEntry.objects.filter(status="waiting").order_by("created_at").first()
    if current:
        current.status = "skipped"
        current.completed_at = timezone.now()
        current.save()
    return redirect("queue_control_dashboard")


@staff_member_required
def toggle_queue_pause(request, queue_id):
    queue = Queue.objects.get(id=queue_id)
    queue.is_paused = not queue.is_paused
    queue.save()
    return redirect("queue_control_dashboard", queue_id=queue.id)

