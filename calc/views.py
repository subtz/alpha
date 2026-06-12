# ==================================================
# IMPORTS
# ==================================================
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.core.paginator import Paginator

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django import forms
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
import json
from django.views.decorators.http import require_POST

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from .models import (
    Queue,
    Customer,
    Service,
    QueueEntry,
    ValidStudent,
    StudentProfile,
    NotificationLog  # Import the new model
)
from .models import PushSubscription
from django.db.models import Avg, F, ExpressionWrapper, DurationField
from .utils import call_groq_api

# ==================================================
# FORMS
# ==================================================
class StudentRegistrationForm(UserCreationForm):
    registration_number = forms.CharField(max_length=50, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = (
            'username',
            'registration_number',
            'email',
            'password1',
            'password2'
        )

    def clean_email(self):
        email = self.cleaned_data.get('email')

        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already exists.")

        return email

    def clean_registration_number(self):
        reg_no = self.cleaned_data.get('registration_number')

        student = ValidStudent.objects.filter(
            registration_number=reg_no,
            is_active=True
        ).first()

        if not student:
            raise forms.ValidationError("Invalid registration number.")

        if StudentProfile.objects.filter(valid_student=student).exists():
            raise forms.ValidationError("This registration number already has an account.")

        return reg_no


# ==================================================
# BASIC PAGES
# ==================================================
def home(request):
    return render(request, 'calc/home.html')


def base(request):
    return render(request, 'calc/base.html')


@login_required
def dashboard(request):
    profile = StudentProfile.objects.filter(user=request.user).first()

    return render(request, 'calc/dashboard.html', {
        'student_profile': profile
    })


# ==================================================
# AUTH
# ==================================================
def register(request):
    form = StudentRegistrationForm()

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)

        if form.is_valid():
            reg_no = form.cleaned_data['registration_number']

            student = ValidStudent.objects.get(
                registration_number=reg_no
            )

            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.is_active = False
            user.save()

            StudentProfile.objects.create(
                user=user,
                valid_student=student
            )

            # Generate verification token and send email
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            verify_path = reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
            verify_url = request.build_absolute_uri(verify_path)

            subject = 'Verify your SQMS account email'
            message = f"Hi {user.username},\n\nPlease verify your email by clicking the link below:\n{verify_url}\n\nIf you did not register, ignore this email."
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com')
            send_mail(subject, message, from_email, [user.email], fail_silently=False)

            return render(request, 'calc/verify_email_sent.html', {'email': user.email})

    return render(request, 'calc/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password')
        )

        if user:
            if not user.is_active:
                # Re-send verification token and email, then show the verification-sent page
                try:
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    token = default_token_generator.make_token(user)
                    verify_path = reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
                    verify_url = request.build_absolute_uri(verify_path)

                    subject = 'Verify your SQMS account email'
                    message = f"Hi {user.username},\n\nPlease verify your email by clicking the link below:\n{verify_url}\n\nIf you did not request this, ignore this email."
                    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com')
                    send_mail(subject, message, from_email, [user.email], fail_silently=False)
                except Exception:
                    # don't block login flow on email errors; fall back to showing the page
                    pass

                return render(request, 'calc/verify_email_sent.html', {'email': user.email})

            login(request, user)
            return redirect('dashboard')

        return HttpResponse("Invalid credentials")

    # Optional inactive notice support via GET param (e.g. /login/?inactive=1)
    inactive_notice = None
    if request.GET.get('inactive'):
        inactive_notice = 'Account inactive. Please verify your email.'

    return render(request, 'calc/login.html', {'inactive_notice': inactive_notice})


def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        return render(request, 'calc/email_verified.html', {'user': user})
    else:
        return HttpResponse('Invalid verification link', status=400)


# ==================================================
# QUEUES
# ==================================================
@login_required
def queue_list(request):
    profile = StudentProfile.objects.filter(user=request.user).first()

    if not profile:
        return HttpResponse("Student profile missing")

    year = str(profile.valid_student.year_of_study)

    queues = []
    for q in Queue.objects.filter(is_active=True):
        allowed = [y.strip() for y in (q.allowed_years or "").split(",") if y.strip()]

        if year in allowed:
            queues.append(q)

    return render(request, 'calc/queue_list.html', {'queues': queues})


# ==================================================
# FIXED SAFE JOIN QUEUE (500 ERROR FIX)
# ==================================================
@login_required
def join_queue(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)

    if queue.is_paused:
        return HttpResponse("Queue is paused")

    profile = StudentProfile.objects.filter(user=request.user).first()
    if not profile:
        return HttpResponse("Student profile missing")

    year = str(profile.valid_student.year_of_study)

    allowed = [y.strip() for y in (queue.allowed_years or "").split(",") if y.strip()]

    if year not in allowed:
        return HttpResponse("You are not allowed to join this queue.")

    # prevent duplicates
    existing = QueueEntry.objects.filter(
        customer__email=request.user.email,
        queue=queue,
        status__in=['waiting', 'serving']
    ).first()

    if existing:
        pos_in_queue = 1
        if existing.status == 'waiting':
            waiting_entries = list(QueueEntry.objects.filter(queue=queue, status='waiting').order_by('entered_at'))
            for idx, entry in enumerate(waiting_entries, start=1):
                if entry.id == existing.id:
                    pos_in_queue = idx
                    break
        avg_service_time = get_avg_service_time_minutes()
        existing_eta = round(avg_service_time * (pos_in_queue - 1), 2)
        return render(request, 'calc/queue_join_success.html', {
            'entry': existing,
            'queue': queue,
            'position': existing.position,
            'eta_minutes': existing_eta,
            'message': 'Already joined.'
        })

    customer, _ = Customer.objects.get_or_create(
        email=request.user.email,
        defaults={'name': request.user.username}
    )

    # capacity check
    if QueueEntry.objects.filter(queue=queue, status__in=['waiting', 'serving']).count() >= queue.max_capacity:
        return HttpResponse("Queue is full")

    service = Service.objects.filter(is_active=True).first()
    if not service:
        return HttpResponse("No active service available.")

    service_time = service.estimated_time or 5

    try:
        with transaction.atomic():
            queue_locked = Queue.objects.select_for_update().get(id=queue.id)
            next_position = queue_locked.current_ticket_number + 1
            queue_locked.current_ticket_number = next_position
            queue_locked.save()

            entry = QueueEntry.objects.create(
                queue=queue_locked,
                customer=customer,
                service=service,
                position=next_position,
                ticket_number=f"SC-{next_position:03d}",
                status='waiting'
            )

    except IntegrityError:
        # fallback
        with transaction.atomic():
            queue_locked = Queue.objects.select_for_update().get(id=queue.id)
            next_position = queue_locked.current_ticket_number + 1
            queue_locked.current_ticket_number = next_position
            queue_locked.save()

            entry = QueueEntry.objects.create(
                queue=queue_locked,
                customer=customer,
                service=service,
                position=next_position,
                ticket_number=f"SC-{next_position:03d}",
                status='waiting'
            )

    avg_service_time = get_avg_service_time_minutes()
    waiting_count = QueueEntry.objects.filter(queue=queue, status='waiting').count()
    eta_minutes = round(avg_service_time * (waiting_count - 1), 2)

    if waiting_count == 1:
        send_student_notification(entry, "You are next in line")

    return render(request, 'calc/queue_join_success.html', {
        'entry': entry,
        'queue': queue,
        'position': entry.position,
        'eta_minutes': eta_minutes
    })


def send_student_notification(entry, message_text):
    try:
        user = User.objects.filter(email=entry.customer.email).first()
        if not user:
            logger.warning(f"No User found for customer email {entry.customer.email}. Notification skipped.")
            return {"success": False, "error": "No User found for email"}

        subscriptions = PushSubscription.objects.filter(user=user)
        if not subscriptions.exists():
            logger.info(f"User {user.username} has no push subscriptions. Notification skipped.")
            return {"success": False, "error": "User has no push subscriptions"}

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": message_text}]
        }
        
        logger.info(f"Dispatching notification to {user.username} ({user.email}) with message: {message_text}")
        result = call_groq_api(payload)
        
        if result.get("success"):
            logger.info(f"Successfully dispatched notification to {user.username} ({user.email}). Groq Response: {result.get('response')}")
        else:
            logger.error(f"Failed to dispatch notification to {user.username} ({user.email}). Error: {result.get('error')}")

        # Save log entry
        NotificationLog.objects.create(
            user=user,
            email=user.email,
            message_text=message_text,
            success=result.get("success"),
            error=result.get("error")
        )

        return result
    except Exception as e:
        logger.error(f"Unexpected exception in send_student_notification for customer email {entry.customer.email}: {e}")
        # Save log entry for unexpected errors
        NotificationLog.objects.create(
            user=user if user else None,
            email=entry.customer.email,
            message_text=message_text,
            success=False,
            error=str(e)
        )
        return {"success": False, "error": str(e)}


def get_avg_service_time_minutes():
    served_entries = QueueEntry.objects.filter(
        status='served',
        served_at__isnull=False,
        entered_at__isnull=False
    )
    total_seconds = 0
    count = 0
    for entry in served_entries:
        diff = entry.served_at - entry.entered_at
        total_seconds += diff.total_seconds()
        count += 1
    
    if count > 0:
        return (total_seconds / count) / 60.0
    return 5.0


def get_waiting_entries(queue):
    waiting_entries = list(QueueEntry.objects.filter(queue=queue, status='waiting').order_by('entered_at'))

    avg_service_time = get_avg_service_time_minutes()

    for idx, entry in enumerate(waiting_entries, start=1):
        entry.position = idx
        entry.eta_minutes = round(avg_service_time * (idx - 1), 2)

    return waiting_entries


# ==================================================
# ANALYTICS
# ==================================================
@staff_member_required
def analytics_dashboard(request):
    """Show average wait time, average service time, and total served.

    Optionally filter by queue via GET param `queue_id`.
    Only uses entries with status='served' and non-null timestamps.
    """
    queue = None
    queue_id = request.GET.get('queue_id')
    if queue_id:
        try:
            queue = Queue.objects.get(id=queue_id)
        except Queue.DoesNotExist:
            queue = None

    entries = QueueEntry.objects.filter(
        status='served',
        served_at__isnull=False,
        entered_at__isnull=False,
        completed_at__isnull=False
    )

    if queue:
        entries = entries.filter(queue=queue)

    # Aggregations using Duration expressions
    wait_expr = ExpressionWrapper(F('served_at') - F('entered_at'), output_field=DurationField())
    service_expr = ExpressionWrapper(F('completed_at') - F('served_at'), output_field=DurationField())

    aggs = entries.aggregate(
        avg_wait=Avg(wait_expr),
        avg_service=Avg(service_expr)
    )

    avg_wait = aggs.get('avg_wait')
    avg_service = aggs.get('avg_service')

    def minutes(td):
        if not td:
            return None
        try:
            return round(td.total_seconds() / 60.0, 2)
        except Exception:
            return None

    context = {
        'queue': queue,
        'avg_wait_minutes': minutes(avg_wait),
        'avg_service_minutes': minutes(avg_service),
        'total_served': entries.count(),
        'queues': Queue.objects.filter(is_active=True)
    }

    return render(request, 'calc/analytics_dashboard.html', context)


# ==================================================
# DISPLAY SCREEN (FIXED)
# ==================================================
@login_required
def queue_display(request):
    queue = Queue.objects.filter(is_active=True).first()

    if not queue:
        return HttpResponse("No active queue available.")

    waiting_list = get_waiting_entries(queue)

    return render(request, 'calc/display.html', {
        'queue': queue,
        'now_serving': QueueEntry.objects.filter(
            queue=queue,
            status='serving'
        ).first(),
        'next_ticket': waiting_list[0] if waiting_list else None,
        'waiting_list': waiting_list
    })


# ==================================================
# STAFF
# ==================================================
@staff_member_required
def staff_dashboard_home(request):
    queues = Queue.objects.filter(is_active=True)

    return render(request, 'calc/staff_dashboard_home.html', {
        'queues': queues
    })


@staff_member_required
def queue_control_dashboard(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)

    page_number = request.GET.get('page', 1)
    log_entries = NotificationLog.objects.all()
    paginator = Paginator(log_entries, 20)  # 20 logs per page
    page_obj = paginator.get_page(page_number)

    return render(request, 'calc/admin_queue_dashboard.html', {
        'queue': queue,
        'current_entry': QueueEntry.objects.filter(queue=queue, status='serving').first(),
        'waiting_list': get_waiting_entries(queue),
        'queue_paused': queue.is_paused,
        'page_obj': page_obj,
    })

@staff_member_required
def get_notification_logs(request):
    page_number = request.GET.get('page', 1)
    student_name = request.GET.get('student_name')
    status_filter = request.GET.get('status')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    log_entries = NotificationLog.objects.all()

    if student_name:
        log_entries = log_entries.filter(user__username__icontains=student_name)
    if status_filter in ['success', 'failure']:
        log_entries = log_entries.filter(success=(status_filter == 'success'))
    if start_date_str:
        start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        log_entries = log_entries.filter(timestamp__date__gte=start_date)
    if end_date_str:
        end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        log_entries = log_entries.filter(timestamp__date__lte=end_date)

    # Summary stats
    total_notifications = log_entries.count()
    success_count = log_entries.filter(success=True).count()
    failure_count = total_notifications - success_count

    paginator = Paginator(log_entries, 20)  # 20 logs per page
    page_obj = paginator.get_page(page_number)
    
    logs_data = []
    for log in page_obj:
        logs_data.append({
            "timestamp": log.timestamp.isoformat(),
            "student": log.user.username if log.user else "N/A",
            "email": log.email,
            "message": log.message_text,
            "status": "Success" if log.success else "Failure",
            "error": log.error
        })
    return JsonResponse({
        "logs": logs_data,
        "num_pages": paginator.num_pages,
        "current_page": page_obj.number,
        "has_next": page_obj.has_next,
        "has_previous": page_obj.has_previous,
        "total_notifications": total_notifications,
        "success_count": success_count,
        "failure_count": failure_count,
    })


@login_required
@require_POST
def queue_status_api(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)

    current = QueueEntry.objects.filter(queue=queue, status='serving').first()
    waiting_entries = get_waiting_entries(queue)

    current_data = None
    if current:
        current_data = {
            'ticket_number': current.ticket_number,
            'customer_name': current.customer.name,
        }

    waiting_data = [
        {
            'position': entry.position,
            'ticket_number': entry.ticket_number,
            'customer_name': entry.customer.name,
            'status': entry.status,
            'eta': entry.eta_minutes,
        }
        for entry in waiting_entries
    ]

    return JsonResponse({
        'current_entry': current_data,
        'waiting_list': waiting_data,
        'queue_paused': queue.is_paused,
        'auto_mode_enabled': queue.is_auto_mode_enabled,
        'auto_serve_interval': queue.auto_serve_interval,
    })


@login_required
@require_POST
def save_push_subscription(request):
    """Save or update push subscription for the logged-in user.

    Expects JSON body: { subscription: { endpoint: ..., keys: { p256dh: ..., auth: ... } } }
    """
    try:
        payload = json.loads(request.body.decode('utf-8'))
        sub = payload.get('subscription')

        if not sub or not sub.get('endpoint'):
            return JsonResponse({'error': 'invalid_subscription'}, status=400)

        endpoint = sub.get('endpoint')
        keys = sub.get('keys', {})
        p256dh = keys.get('p256dh', '')
        auth_key = keys.get('auth', '')

        obj, created = PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=endpoint,
            defaults={'p256dh': p256dh, 'auth_key': auth_key}
        )

        return JsonResponse({'status': 'ok', 'created': created})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def advance_queue(queue_id):
    now = timezone.now()

    current = QueueEntry.objects.filter(queue_id=queue_id, status='serving').first()

    if current:
        current.status = 'served'
        current.completed_at = now
        current.served_at = current.served_at or now
        current.save()

    next_entry = QueueEntry.objects.filter(queue_id=queue_id, status='waiting').order_by('position').first()

    if next_entry:
        next_entry.status = 'serving'
        next_entry.served_at = now
        next_entry.save()
        send_student_notification(next_entry, "You are now being served")

    new_next_in_line = QueueEntry.objects.filter(queue_id=queue_id, status='waiting').order_by('position').first()
    if new_next_in_line:
        send_student_notification(new_next_in_line, "You are next in line")


@staff_member_required
def serve_current(request, queue_id):
    advance_queue(queue_id)
    return redirect('queue_control_dashboard', queue_id=queue_id)


@staff_member_required
def skip_current(request, queue_id):
    entry = QueueEntry.objects.filter(queue_id=queue_id, status='serving').first()

    if entry:
        entry.status = 'skipped'
        entry.completed_at = timezone.now()
        entry.save()

    return redirect('queue_control_dashboard', queue_id=queue_id)


@staff_member_required
def toggle_queue_pause(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)
    queue.is_paused = not queue.is_paused
    queue.save()

    return redirect('queue_control_dashboard', queue_id=queue_id)


@staff_member_required
def toggle_auto_mode(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)

    if request.method == 'POST':
        queue.is_auto_mode_enabled = not queue.is_auto_mode_enabled
        if queue.is_auto_mode_enabled:
            queue.last_auto_served_at = timezone.now()
        queue.save()

    return redirect('queue_control_dashboard', queue_id=queue_id)


@staff_member_required
def set_auto_interval(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)

    if request.method == 'POST':
        interval = request.POST.get('auto_serve_interval')
        try:
            interval_value = int(interval)
            if interval_value > 0:
                queue.auto_serve_interval = interval_value
                if queue.is_auto_mode_enabled:
                    queue.last_auto_served_at = timezone.now()
                queue.save()
        except (TypeError, ValueError):
            pass

    return redirect('queue_control_dashboard', queue_id=queue_id)


# ==================================================
# REPORTS
# ==================================================
@staff_member_required
def staff_reports(request):
    today = timezone.localdate()

    return render(request, 'calc/staff_reports.html', {
        'today': today,
        'served_today': QueueEntry.objects.filter(status='served', completed_at__date=today).count(),
        'waiting': QueueEntry.objects.filter(status='waiting').count(),
        'skipped': QueueEntry.objects.filter(status='skipped', completed_at__date=today).count()
    })


@staff_member_required
def export_reports_pdf(request):
    today = timezone.localdate()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="report_{today}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter)
    styles = getSampleStyleSheet()

    elements = [
        Paragraph("Queue Report", styles['Title']),
        Spacer(1, 20)
    ]

    data = [
        ['Metric', 'Value'],
        ['Date', str(today)],
        ['Waiting', QueueEntry.objects.filter(status='waiting').count()],
        ['Served Today', QueueEntry.objects.filter(status='served', completed_at__date=today).count()],
        ['Skipped', QueueEntry.objects.filter(status='skipped', completed_at__date=today).count()]
    ]

    table = Table(data)
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    doc.build(elements)

    return response


@staff_member_required
@require_POST
def send_test_push(request):
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{
            "role": "user",
            "content": "Test notification from SQMS"
        }]
    }
    groq_response = call_groq_api(payload)
    return JsonResponse(groq_response)
