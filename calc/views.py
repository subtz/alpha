# ==================================================
# CORE IMPORTS
# ==================================================
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.db import transaction

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django import forms

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet

from .models import (
    Queue,
    Customer,
    Service,
    QueueEntry,
    ValidStudent,
    StudentProfile
)

# ==================================================
# FORMS
# ==================================================
class StudentRegistrationForm(UserCreationForm):

    registration_number = forms.CharField(
        max_length=50
    )

    email = forms.EmailField(
        required=True
    )

    class Meta:

        model = User

        fields = (
            'registration_number',
            'username',
            'email',
            'password1',
            'password2'
        )


# ==================================================
# BASIC PAGES
# ==================================================
def home(request):

    return render(
        request,
        'calc/home.html'
    )


def base(request):

    return render(
        request,
        'calc/base.html'
    )


@login_required
def dashboard(request):

    profile = StudentProfile.objects.filter(
        user=request.user
    ).first()

    return render(
        request,
        'calc/dashboard.html',
        {
            'student_profile': profile
        }
    )


# ==================================================
# AUTH
# ==================================================
def register(request):

    if request.method == 'POST':

        form = StudentRegistrationForm(
            request.POST
        )

        reg_no = request.POST.get(
            'registration_number'
        )

        try:

            valid_student = ValidStudent.objects.get(
                registration_number=reg_no,
                is_active=True
            )

        except ValidStudent.DoesNotExist:

            return HttpResponse(
                "Invalid registration number"
            )

        if form.is_valid():

            user = form.save(
                commit=False
            )

            user.email = form.cleaned_data[
                'email'
            ]

            user.save()

            StudentProfile.objects.create(
                user=user,
                valid_student=valid_student
            )

            login(
                request,
                user
            )

            return redirect(
                'dashboard'
            )

    else:

        form = StudentRegistrationForm()

    return render(
        request,
        'calc/register.html',
        {
            'form': form
        }
    )


def login_view(request):

    if request.method == 'POST':

        user = authenticate(
            request,
            username=request.POST.get(
                'username'
            ),
            password=request.POST.get(
                'password'
            )
        )

        if user:

            login(
                request,
                user
            )

            return redirect(
                'dashboard'
            )

        return HttpResponse(
            "Invalid credentials"
        )

    return render(
        request,
        'calc/login.html'
    )


# ==================================================
# STUDENT QUEUES
# ==================================================
@login_required
def queue_list(request):

    profile = StudentProfile.objects.filter(
        user=request.user
    ).first()

    if not profile:

        return HttpResponse(
            "Student profile missing"
        )

    student_year = str(
        profile.valid_student.year_of_study
    )

    queues = []

    all_queues = Queue.objects.filter(
        is_active=True
    )

    for queue in all_queues:

        allowed_years_raw = (
            queue.allowed_years or ""
        )

        allowed_years = [
            year.strip()
            for year in allowed_years_raw.split(',')
            if year.strip()
        ]

        if student_year in allowed_years:

            queues.append(queue)

    return render(
        request,
        'calc/queue_list.html',
        {
            'queues': queues
        }
    )


@login_required
def join_queue(request, queue_id):

    queue = get_object_or_404(
        Queue,
        id=queue_id
    )

    if queue.is_paused:

        return HttpResponse(
            "Queue is paused"
        )

    profile = StudentProfile.objects.filter(
        user=request.user
    ).first()

    if not profile:

        return HttpResponse(
            "Student profile missing"
        )

    student_year = str(
        profile.valid_student.year_of_study
    )

    allowed_years_raw = (
        queue.allowed_years or ""
    )

    allowed_years = [
        year.strip()
        for year in allowed_years_raw.split(',')
        if year.strip()
    ]

    if student_year not in allowed_years:

        return HttpResponse(
            "You are not allowed to join this queue."
        )

    existing_entry = QueueEntry.objects.filter(
        customer__email=request.user.email,
        queue=queue,
        status__in=[
            'waiting',
            'serving'
        ]
    ).first()

    if existing_entry:

        return render(
            request,
            'calc/queue_join_success.html',
            {
                'entry': existing_entry,
                'queue': queue,
                'message': 'Already joined.'
            }
        )

    customer, created = Customer.objects.get_or_create(
        email=request.user.email,

        defaults={
            'name': request.user.username
        }
    )

    current_count = QueueEntry.objects.filter(
        queue=queue,
        status__in=[
            'waiting',
            'serving'
        ]
    ).count()

    if current_count >= queue.max_capacity:

        return HttpResponse(
            "Queue is full"
        )

    service = Service.objects.filter(
        is_active=True
    ).first()

    if not service:

        return HttpResponse(
            "No active service available."
        )

    with transaction.atomic():

        last = QueueEntry.objects.filter(
            queue=queue
        ).order_by(
            '-position'
        ).first()

        next_position = (
            last.position + 1
            if last else 1
        )

        entry = QueueEntry.objects.create(
            queue=queue,
            customer=customer,
            service=service,
            position=next_position,
            status='waiting'
        )

    return render(
        request,
        'calc/queue_join_success.html',
        {
            'entry': entry,
            'queue': queue
        }
    )


# ==================================================
# LIVE DISPLAY
# ==================================================
@login_required
def queue_display(request):

    queue = Queue.objects.filter(
        is_active=True
    ).first()

    return render(
        request,
        'calc/display.html',
        {
            'queue': queue,
            'now_serving': QueueEntry.objects.filter(
                queue=queue,
                status='serving'
            ).first() if queue else None,

            'next_ticket': QueueEntry.objects.filter(
                queue=queue,
                status='waiting'
            ).order_by(
                'position'
            ).first() if queue else None
        }
    )


# ==================================================
# STAFF DASHBOARD
# ==================================================
@staff_member_required
def staff_dashboard_home(request):

    queues = Queue.objects.filter(
        is_active=True
    )

    return render(
        request,
        'calc/staff_dashboard_home.html',
        {
            'queues': queues
        }
    )


@staff_member_required
def queue_control_dashboard(request, queue_id):

    queue = get_object_or_404(
        Queue,
        id=queue_id
    )

    current_entry = QueueEntry.objects.filter(
        queue=queue,
        status='serving'
    ).first()

    waiting_list = QueueEntry.objects.filter(
        queue=queue,
        status='waiting'
    ).order_by(
        'position'
    )

    return render(
        request,
        'calc/admin_queue_dashboard.html',
        {
            'queue': queue,
            'current_entry': current_entry,
            'waiting_list': waiting_list,
            'queue_paused': queue.is_paused
        }
    )


# ==================================================
# STAFF ACTIONS
# ==================================================
@staff_member_required
def serve_current(request, queue_id):

    now = timezone.now()

    current = QueueEntry.objects.filter(
        queue_id=queue_id,
        status='serving'
    ).first()

    if current:

        current.status = 'completed'

        current.completed_at = now

        if not current.served_at:

            current.served_at = now

        current.save()

    next_entry = QueueEntry.objects.filter(
        queue_id=queue_id,
        status='waiting'
    ).order_by(
        'position'
    ).first()

    if next_entry:

        next_entry.status = 'serving'

        next_entry.served_at = now

        next_entry.save()

    return redirect(
        'queue_control_dashboard',
        queue_id=queue_id
    )


@staff_member_required
def skip_current(request, queue_id):

    entry = QueueEntry.objects.filter(
        queue_id=queue_id,
        status='serving'
    ).first()

    if entry:

        entry.status = 'skipped'

        entry.completed_at = timezone.now()

        entry.save()

    return redirect(
        'queue_control_dashboard',
        queue_id=queue_id
    )


@staff_member_required
def toggle_queue_pause(request, queue_id):

    queue = get_object_or_404(
        Queue,
        id=queue_id
    )

    queue.is_paused = not queue.is_paused

    queue.save()

    return redirect(
        'queue_control_dashboard',
        queue_id=queue_id
    )


# ==================================================
# REPORTS
# ==================================================
@staff_member_required
def staff_reports(request):

    today = timezone.localdate()

    served_today = QueueEntry.objects.filter(
        status='completed',
        completed_at__date=today
    ).count()

    waiting = QueueEntry.objects.filter(
        status='waiting'
    ).count()

    skipped = QueueEntry.objects.filter(
        status='skipped'
    ).count()

    return render(
        request,
        'calc/staff_reports.html',
        {
            'today': today,
            'served_today': served_today,
            'waiting': waiting,
            'skipped': skipped
        }
    )


@staff_member_required
def export_reports_pdf(request):

    today = timezone.localdate()

    response = HttpResponse(
        content_type='application/pdf'
    )

    response[
        'Content-Disposition'
    ] = f'attachment; filename="report_{today}.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=letter
    )

    styles = getSampleStyleSheet()

    elements = [

        Paragraph(
            "Queue Report",
            styles['Title']
        ),

        Spacer(1, 20)
    ]

    data = [

        ['Metric', 'Value'],

        ['Date', str(today)],

        ['Waiting',
         QueueEntry.objects.filter(
             status='waiting'
         ).count()
         ],

        ['Served Today',
         QueueEntry.objects.filter(
             status='completed',
             completed_at__date=today
         ).count()
         ],

        ['Skipped',
         QueueEntry.objects.filter(
             status='skipped'
         ).count()
         ]
    ]

    table = Table(data)

    table.setStyle(
        TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
    )

    elements.append(table)

    doc.build(elements)

    return response