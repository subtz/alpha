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
from django.core.cache import cache
from django.contrib import messages

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
import os
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
    NotificationLog
)
from .models import PushSubscription
from django.db.models import Avg, F, ExpressionWrapper, DurationField
from .utils import call_groq_api


# ==================================================
# FORMS
# ==================================================
class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['profile_picture']

    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if picture:
            if picture.size > 2 * 1024 * 1024:
                raise forms.ValidationError(
                    "Image file too large. Maximum size is 2MB."
                )
            allowed_types = ['image/jpeg', 'image/png']
            if picture.content_type not in allowed_types:
                raise forms.ValidationError(
                    "Unsupported file type. Please upload a JPEG or PNG image."
                )
        return picture



@login_required
def profile_picture_upload(request):
    student_profile = get_object_or_404(StudentProfile, user=request.user)
    if request.method == 'POST':
        form = ProfilePictureForm(request.POST, request.FILES, instance=student_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile picture updated successfully!')
            return redirect('dashboard')  # Redirect to a relevant page, e.g., dashboard or profile view
        else:
            messages.error(request, 'Error uploading profile picture. Please check the file type and size.')
    else:
        form = ProfilePictureForm(instance=student_profile)

    return render(request, 'sqms/profile_picture_upload.html', {
        'form': form,
        'student_profile': student_profile
    })


@login_required
@require_POST
def update_profile_picture(request):
    student_profile = get_object_or_404(StudentProfile, user=request.user)
    form = ProfilePictureForm(request.POST, request.FILES, instance=student_profile)
    if form.is_valid():
        form.save()
        messages.success(request, 'Profile picture updated successfully!')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'image_url': student_profile.profile_picture.url
            })
        return redirect('dashboard')

    messages.error(request, 'Error updating profile picture. Please check the file type and size.')
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        errors = {
            field: [str(error) for error in error_list]
            for field, error_list in form.errors.items()
        }
        return JsonResponse({
            'success': False,
            'errors': errors
        }, status=400)

    return render(request, 'sqms/profile_picture_upload.html', {
        'form': form,
        'student_profile': student_profile
    })


def service_worker(request):
    sw_path = os.path.join(settings.BASE_DIR, 'sqms', 'static', 'sqms', 'service-worker.js')
    try:
        with open(sw_path, 'r', encoding='utf-8') as sw_file:
            content = sw_file.read()
    except FileNotFoundError:
        content = '// Service worker file not found.'
    return HttpResponse(content, content_type='application/javascript')


def offline(request):
    return HttpResponse(
        '<h1>Offline</h1><p>The application is offline. Please reconnect to continue.</p>',
        content_type='text/html'
    )


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
# SECURITY EMAIL HELPER
# ==================================================
def send_security_email(user, event_type):
    now = timezone.now().strftime('%Y-%m-%d %H:%M UTC')

    subjects = {
        'activated': 'Your SQMS account has been activated',
        'password_changed': 'Your SQMS password was changed',
        'new_login': 'New login to your SQMS account',
    }

    messages_body = {
        'activated': (
            f"Hi {user.username},\n\n"
            f"Your SQMS account was successfully activated on {now}.\n\n"
            f"You can now log in at any time.\n\n"
            f"If this was not you, contact support immediately."
        ),
        'password_changed': (
            f"Hi {user.username},\n\n"
            f"Your SQMS password was changed on {now}.\n\n"
            f"If this was not you, reset your password immediately."
        ),
        'new_login': (
            f"Hi {user.username},\n\n"
            f"A new login to your SQMS account was detected on {now}.\n\n"
            f"If this was not you, reset your password immediately."
        ),
    }

    subject = subjects.get(event_type, 'SQMS Security Notice')
    body = messages_body.get(event_type, '')
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@sqms.com')

    try:
        send_mail(subject, body, from_email, [user.email], fail_silently=True)
    except Exception as e:
        logger.error(f"Security email ({event_type}) failed for {user.email}: {e}")


# ==================================================
# AUTH
# ==================================================
def register(request):
    form = StudentRegistrationForm()

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)

        if form.is_valid():
            reg_no = form.cleaned_data['registration_number']
            student = ValidStudent.objects.get(registration_number=reg_no)

            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.is_active = False
            user.save()

            StudentProfile.objects.create(
                user=user,
                valid_student=student
            )

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            verify_path = reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
            verify_url = request.build_absolute_uri(verify_path)

            subject = 'Verify your SQMS account email'
            message = (
                f"Hi {user.username},\n\n"
                f"Please verify your SQMS account by clicking the link below:\n\n"
                f"{verify_url}\n\n"
                f"This link expires in 24 hours.\n\n"
                f"If you did not register, ignore this email."
            )
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@sqms.com')

            try:
                send_mail(subject, message, from_email, [user.email], fail_silently=False)
            except Exception as e:
                logger.error(f"Registration email failed for {user.email}: {e}")
                messages.error(request, "There was an error sending the verification email. Please try again later.")
                user.delete()  # Clean up the created user if email fails
                return render(request, 'sqms/register.html', {
                    'form': form,
                    'error': 'Failed to send verification email. Please try again.'
                })

            messages.success(request, f"A verification email has been sent to {user.email}. Please check your inbox.")
            return render(request, 'sqms/verify_email_sent.html', {'email': user.email})

    return render(request, 'sqms/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password')
        )

        if user:
            if not user.is_active:
                return render(request, 'sqms/verify_email_sent.html', {
                    'email': user.email,
                    'show_resend': True
                })

            login(request, user)
         #   send_security_email(user, 'new_login')
            return redirect('dashboard')

        return render(request, 'sqms/login.html', {
            'error': 'Invalid username or password.'
        })

    inactive_notice = None
    if request.GET.get('inactive'):
        inactive_notice = 'Your account is not verified. Please check your email.'

    return render(request, 'sqms/login.html', {
        'inactive_notice': inactive_notice
    })


def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        send_security_email(user, 'activated')
        return render(request, 'sqms/email_verified.html', {'user': user})
    else:
        return render(request, 'sqms/email_expired.html', status=400)


def resend_confirmation(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()

        cache_key = f'resend_confirm_{email}'
        attempts = cache.get(cache_key, 0)

        if attempts >= 3:
            return render(request, 'sqms/resend_confirmation.html', {
                'error': 'Too many attempts. Please wait an hour before trying again.',
                'email': email
            })

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return render(request, 'sqms/resend_confirmation.html', {
                'success': True,
                'email': email
            })

        if user.is_active:
            return render(request, 'sqms/resend_confirmation.html', {
                'error': 'This account is already verified. You can log in.',
                'email': email
            })

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        verify_path = reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
        verify_url = request.build_absolute_uri(verify_path)

        subject = 'Verify your SQMS account email'
        message = (
            f"Hi {user.username},\n\n"
            f"Here is your new verification link:\n\n"
            f"{verify_url}\n\n"
            f"This link expires in 24 hours.\n\n"
            f"If you did not register, ignore this email."
        )
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@sqms.com')

        try:
            send_mail(subject, message, from_email, [user.email], fail_silently=False)
        except Exception as e:
            logger.error(f"Resend confirmation failed for {email}: {e}")
            messages.error(request, "Failed to send email. Please try again later.")
            return render(request, 'sqms/resend_confirmation.html', {
                'error': 'Failed to send email. Please try again later.',
                'email': email
            })

        cache.set(cache_key, attempts + 1, timeout=3600)
        messages.success(request, f"A new verification email has been sent to {email}. Please check your inbox.")

        return render(request, 'sqms/resend_confirmation.html', {
            'success': True,
            'email': email
        })

    return render(request, 'sqms/resend_confirmation.html')


def home(request):
    try:
        return render(request, 'sqms/home.html')
    except Exception:
        logger.exception('Unhandled exception in home view')
        raise


def base(request):
    return render(request, 'sqms/base.html')


@login_required
def dashboard(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    form = ProfilePictureForm(instance=profile) if profile else None
    return render(request, 'sqms/dashboard.html', {
        'student_profile': profile,
        'profile_picture_form': form
    })


# ==================================================
# NOTIFICATIONS
# ==================================================
@login_required
def student_queue_status(request):
    entry = QueueEntry.objects.filter(
        customer__email=request.user.email,
        status__in=['waiting', 'serving']
    ).select_related('queue').first()

    if not entry:
        return JsonResponse({
            'in_queue': False,
            'message': 'You are not currently in any queue.'
        })

    process_auto_mode(entry.queue)
    entry.refresh_from_db()

    waiting_entries = list(
        QueueEntry.objects.filter(
            queue=entry.queue,
            status='waiting'
        ).order_by('entered_at')
    )

    position = None
    for idx, e in enumerate(waiting_entries, start=1):
        if e.id == entry.id:
            position = idx
            break

    if entry.status == 'serving':
        position = 1
        tickets_ahead = 0
    else:
        tickets_ahead = (position - 1) if position else 0

    avg_service_time = get_avg_service_time_minutes()
    eta_minutes = round(avg_service_time * tickets_ahead, 2)

    return JsonResponse({
        'in_queue': True,
        'status': entry.status,
        'ticket_number': entry.ticket_number,
        'position': position,
        'tickets_ahead': tickets_ahead,
        'eta_minutes': eta_minutes,
        'queue_name': entry.queue.name,
        'is_being_served': entry.status == 'serving',
    })


@login_required
def notifications_page(request):
    # Mark user's notification logs as read when they visit notifications/status page
    NotificationLog.objects.filter(user=request.user, is_read=False).update(is_read=True)

    entry = QueueEntry.objects.filter(
        customer__email=request.user.email,
        status__in=['waiting', 'serving']
    ).select_related('queue').first()

    return render(request, 'sqms/notifications.html', {
        'entry': entry
    })


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

    return render(request, 'sqms/queue_list.html', {'queues': queues})


# ==================================================
# JOIN QUEUE
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

    existing = QueueEntry.objects.filter(
        customer__email=request.user.email,
        queue=queue,
        status__in=['waiting', 'serving']
    ).first()

    if existing:
        queue_position = 1
        if existing.status == 'waiting':
            waiting_entries = get_waiting_entries(queue)
            queue_position = 1
            for idx, entry in enumerate(waiting_entries, start=1):
                if entry.id == existing.id:
                    queue_position = idx
                    break
        avg_service_time = get_avg_service_time_minutes()
        existing_eta = round(avg_service_time * (queue_position - 1), 2)
        return render(request, 'sqms/queue_join_success.html', {
            'entry': existing,
            'queue': queue,
            'ticket_number': existing.ticket_number,
            'queue_position': queue_position,
            'position': queue_position,
            'eta_minutes': existing_eta,
            'message': 'Already joined.'
        })

    customer, _ = Customer.objects.get_or_create(
        email=request.user.email,
        defaults={'name': request.user.username}
    )

    if QueueEntry.objects.filter(
        queue=queue, status__in=['waiting', 'serving']
    ).count() >= queue.max_capacity:
        return HttpResponse("Queue is full")

    service = Service.objects.filter(is_active=True).first()
    if not service:
        return HttpResponse("No active service available.")

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
    waiting_entries = get_waiting_entries(queue)
    queue_position = 1
    for idx, waiting_entry in enumerate(waiting_entries, start=1):
        if waiting_entry.id == entry.id:
            queue_position = idx
            break

    waiting_count = len(waiting_entries)
    eta_minutes = round(avg_service_time * (queue_position - 1), 2)

    # Join queue notification (deep linked to notifications page)
    send_student_notification(
        entry,
        f"You have joined the '{queue.name}' queue. Ticket: {entry.ticket_number}",
        url=reverse("notifications")
    )

    if waiting_count == 1:
        send_student_notification(
            entry,
            "You are next in line! Get ready.",
            url=reverse("notifications")
        )

    return render(request, 'sqms/queue_join_success.html', {
        'entry': entry,
        'queue': queue,
        'ticket_number': entry.ticket_number,
        'queue_position': queue_position,
        'position': queue_position,
        'eta_minutes': eta_minutes
    })


from pywebpush import webpush, WebPushException
import json


def send_student_notification(entry, message_text, url=None):
    try:
        user = User.objects.filter(
            email=entry.customer.email
        ).first()

        if not user:
            return {
                "success": False,
                "error": "User not found"
            }

        subscriptions = PushSubscription.objects.filter(
            user=user
        )

        if not subscriptions.exists():
            return {
                "success": False,
                "error": "No subscriptions"
            }

        success_count = 0

        for sub in list(subscriptions):
            subscription_info = {
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh,
                    "auth": sub.auth_key,
                }
            }

            try:
                webpush(
                    subscription_info=subscription_info,
                    data=json.dumps({
                        "title": "SQMS Notification",
                        "body": message_text,
                        "url": url or "/notifications/"
                    }),
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={
                        "sub": "mailto:admin@sqms.com"
                    }
                )
                success_count += 1

            except WebPushException as e:
                logger.error(
                    f"Push failed for subscription {sub.id}: {e}"
                )
                # Remove invalid subscriptions automatically
                try:
                    if e.response is not None and e.response.status_code in [404, 410]:
                        logger.info(
                            f"Removing expired/invalid subscription {sub.id} for {user.email}"
                        )
                        sub.delete()
                except Exception:
                    pass

        NotificationLog.objects.create(
            user=user,
            email=user.email,
            message_text=message_text,
            success=success_count > 0,
            error="" if success_count > 0 else "Push failed"
        )

        return {
            "success": success_count > 0
        }

    except Exception as e:
        logger.error(f"Failed to send push notification to {entry.customer.email}: {e}")

        # Ensure user can be retrieved safely
        try:
            assoc_user = User.objects.filter(email=entry.customer.email).first()
        except Exception:
            assoc_user = None

        NotificationLog.objects.create(
            user=assoc_user,
            email=entry.customer.email,
            message_text=message_text,
            success=False,
            error=str(e)
        )

        return {
            "success": False,
            "error": str(e)
        }

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
    waiting_entries = list(QueueEntry.objects.filter(
        queue=queue, status='waiting'
    ).order_by('entered_at'))

    avg_service_time = get_avg_service_time_minutes()

    for idx, entry in enumerate(waiting_entries, start=1):
        entry.position = idx
        entry.eta_minutes = round(avg_service_time * (idx - 1), 2)

    return waiting_entries


def complete_queue_entry(entry, status='served', notification_message=None, now=None):
    if not entry:
        return None

    now = now or timezone.now()
    entry.status = status
    entry.completed_at = now
    entry.served_at = entry.served_at or now
    entry.save()

    if notification_message:
        send_student_notification(
            entry,
            notification_message,
            url=reverse("notifications")
        )

    return entry


def serve_next_waiting(queue, now=None):
    now = now or timezone.now()
    next_entry = QueueEntry.objects.filter(
        queue=queue,
        status='waiting'
    ).order_by('entered_at').first()

    if not next_entry:
        return None

    next_entry.status = 'serving'
    next_entry.served_at = now
    next_entry.save()

    send_student_notification(
        next_entry,
        "It's your turn! Please proceed to the service desk now.",
        url=reverse("notifications")
    )

    return next_entry


def notify_waiting_positions(queue):
    waiting_entries = list(QueueEntry.objects.filter(
        queue=queue, status='waiting'
    ).order_by('entered_at'))

    for idx, entry in enumerate(waiting_entries, start=1):
        tickets_ahead = idx - 1
        if tickets_ahead == 0:
            send_student_notification(
                entry,
                "You are next in line! Get ready.",
                url=reverse("notifications")
            )
        elif tickets_ahead == 2:
            send_student_notification(
                entry,
                "Only 3 tickets ahead of you. Please be ready soon.",
                url=reverse("notifications")
            )


def process_auto_mode(queue):
    if not queue.is_auto_mode_enabled or queue.is_paused or queue.auto_serve_interval <= 0:
        return

    now = timezone.now()

    with transaction.atomic():
        queue_locked = Queue.objects.select_for_update().get(id=queue.id)

        if queue_locked.is_paused or not queue_locked.is_auto_mode_enabled:
            return

        current = QueueEntry.objects.select_for_update().filter(
            queue=queue_locked,
            status='serving'
        ).first()

        waiting_entries = list(QueueEntry.objects.select_for_update().filter(
            queue=queue_locked,
            status='waiting'
        ).order_by('entered_at'))

        if not current:
            if waiting_entries:
                serve_next_waiting(queue_locked, now=now)
                queue_locked.last_auto_served_at = now
                queue_locked.save(update_fields=['last_auto_served_at'])
                notify_waiting_positions(queue_locked)
            return

        if queue_locked.last_auto_served_at is None:
            queue_locked.last_auto_served_at = now
            queue_locked.save(update_fields=['last_auto_served_at'])
            return

        interval_delta = timedelta(minutes=queue_locked.auto_serve_interval)
        if now >= queue_locked.last_auto_served_at + interval_delta:
            complete_queue_entry(
                current,
                status='served',
                notification_message="Your service in the queue has been completed. Thank you!",
                now=now
            )
            if waiting_entries:
                serve_next_waiting(queue_locked, now=now)
            queue_locked.last_auto_served_at = now
            queue_locked.save(update_fields=['last_auto_served_at'])
            notify_waiting_positions(queue_locked)


# ==================================================
# ANALYTICS
# ==================================================
@staff_member_required
def analytics_dashboard(request):
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

    wait_expr = ExpressionWrapper(F('served_at') - F('entered_at'), output_field=DurationField())
    service_expr = ExpressionWrapper(F('completed_at') - F('served_at'), output_field=DurationField())

    aggs = entries.aggregate(
        avg_wait=Avg(wait_expr),
        avg_service=Avg(service_expr)
    )

    def minutes(td):
        if not td:
            return None
        try:
            return round(td.total_seconds() / 60.0, 2)
        except Exception:
            return None

    return render(request, 'sqms/analytics_dashboard.html', {
        'queue': queue,
        'avg_wait_minutes': minutes(aggs.get('avg_wait')),
        'avg_service_minutes': minutes(aggs.get('avg_service')),
        'total_served': entries.count(),
        'queues': Queue.objects.filter(is_active=True)
    })


# ==================================================
# DISPLAY SCREEN
# ==================================================
@login_required
def queue_display(request):
    queue = Queue.objects.filter(is_active=True).first()

    if not queue:
        return HttpResponse("No active queue available.")

    waiting_list = get_waiting_entries(queue)

    return render(request, 'sqms/display.html', {
        'queue': queue,
        'now_serving': QueueEntry.objects.filter(queue=queue, status='serving').first(),
        'next_ticket': waiting_list[0] if waiting_list else None,
        'waiting_list': waiting_list
    })


# ==================================================
# STAFF
# ==================================================
@staff_member_required
def staff_dashboard_home(request):
    return render(request, 'sqms/staff_dashboard_home.html', {
        'queues': Queue.objects.filter(is_active=True)
    })


@staff_member_required
def queue_control_dashboard(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)
    log_entries = NotificationLog.objects.all()
    paginator = Paginator(log_entries, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'sqms/admin_queue_dashboard.html', {
        'queue': queue,
        'current_entry': QueueEntry.objects.filter(queue=queue, status='serving').first(),
        'waiting_list': get_waiting_entries(queue),
        'queue_paused': queue.is_paused,
        'page_obj': page_obj,
    })


@staff_member_required
def get_notification_logs(request):
    log_entries = NotificationLog.objects.all()

    student_name = request.GET.get('student_name')
    status_filter = request.GET.get('status')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

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

    total_notifications = log_entries.count()
    success_count = log_entries.filter(success=True).count()

    paginator = Paginator(log_entries, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    logs_data = [{
        "timestamp": log.timestamp.isoformat(),
        "student": log.user.username if log.user else "N/A",
        "email": log.email,
        "message": log.message_text,
        "status": "Success" if log.success else "Failure",
        "error": log.error
    } for log in page_obj]

    return JsonResponse({
        "logs": logs_data,
        "num_pages": paginator.num_pages,
        "current_page": page_obj.number,
        "has_next": page_obj.has_next,
        "has_previous": page_obj.has_previous,
        "total_notifications": total_notifications,
        "success_count": success_count,
        "failure_count": total_notifications - success_count,
    })


@login_required
@require_POST
def queue_status_api(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)
    process_auto_mode(queue)
    queue.refresh_from_db()

    current = QueueEntry.objects.filter(queue=queue, status='serving').first()
    waiting_entries = get_waiting_entries(queue)

    return JsonResponse({
        'current_entry': {
            'ticket_number': current.ticket_number,
            'customer_name': current.customer.name,
        } if current else None,
        'waiting_list': [{
            'position': e.position,
            'ticket_number': e.ticket_number,
            'customer_name': e.customer.name,
            'status': e.status,
            'eta': e.eta_minutes,
        } for e in waiting_entries],
        'queue_paused': queue.is_paused,
        'auto_mode_enabled': queue.is_auto_mode_enabled,
        'auto_serve_interval': queue.auto_serve_interval,
    })


@login_required
@require_POST
def save_push_subscription(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
        sub = payload.get('subscription')

        if not sub or not sub.get('endpoint'):
            return JsonResponse({'error': 'invalid_subscription'}, status=400)

        endpoint = sub.get('endpoint')
        keys = sub.get('keys', {})

        obj, created = PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=endpoint,
            defaults={
                'p256dh': keys.get('p256dh', ''),
                'auth_key': keys.get('auth', '')
            }
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
        # Queue entry completion event trigger
        send_student_notification(
            current,
            f"Your service in the queue has been completed. Thank you!",
            url=reverse("notifications")
        )

    next_entry = QueueEntry.objects.filter(
        queue_id=queue_id, status='waiting'
    ).order_by('entered_at').first()

    if next_entry:
        next_entry.status = 'serving'
        next_entry.served_at = now
        next_entry.save()
        # Student now being served trigger
        send_student_notification(
            next_entry,
            "It's your turn! Please proceed to the service desk now.",
            url=reverse("notifications")
        )

    waiting_entries = list(
        QueueEntry.objects.filter(
            queue_id=queue_id, status='waiting'
        ).order_by('entered_at')
    )

    for idx, entry in enumerate(waiting_entries, start=1):
        tickets_ahead = idx - 1
        if tickets_ahead == 0:
            # Student next in line trigger
            send_student_notification(
                entry,
                "You are next in line! Get ready.",
                url=reverse("notifications")
            )
        elif tickets_ahead == 2:
            send_student_notification(
                entry,
                "Only 3 tickets ahead of you. Please be ready soon.",
                url=reverse("notifications")
            )


@staff_member_required
def serve_current(request, queue_id):
    advance_queue(queue_id)
    queue = Queue.objects.filter(id=queue_id).first()
    if queue and queue.is_auto_mode_enabled:
        queue.last_auto_served_at = timezone.now()
        queue.save(update_fields=['last_auto_served_at'])
    return redirect('queue_control_dashboard', queue_id=queue_id)


@staff_member_required
def skip_current(request, queue_id):
    with transaction.atomic():
        queue = Queue.objects.select_for_update().filter(id=queue_id).first()
        entry = QueueEntry.objects.select_for_update().filter(
            queue_id=queue_id, status='serving'
        ).first()
        if entry:
            entry.status = 'skipped'
            entry.completed_at = timezone.now()
            entry.save()
            send_student_notification(
                entry,
                f"Your ticket {entry.ticket_number} has been skipped.",
                url=reverse("notifications")
            )
            if queue and queue.is_auto_mode_enabled:
                queue.last_auto_served_at = timezone.now()
                queue.save(update_fields=['last_auto_served_at'])
            serve_next_waiting(queue)
            notify_waiting_positions(queue)
    return redirect('queue_control_dashboard', queue_id=queue_id)


@staff_member_required
def toggle_queue_pause(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)
    queue.is_paused = not queue.is_paused
    queue.save()

    # Paused / Resumed trigger
    status_message = "paused" if queue.is_paused else "resumed"
    entries_in_queue = QueueEntry.objects.filter(
        queue=queue, status__in=["waiting", "serving"]
    )
    for entry in entries_in_queue:
        send_student_notification(
            entry,
            f"The '{queue.name}' queue has been {status_message}.",
            url=reverse("notifications")
        )

    return redirect('queue_control_dashboard', queue_id=queue_id)


@staff_member_required
def toggle_auto_mode(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)
    if request.method == 'POST':
        if not queue.is_auto_mode_enabled and queue.auto_serve_interval <= 0:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'auto_interval_required',
                    'message': 'Please set a positive auto serve interval before enabling Auto Mode.'
                }, status=400)
            return redirect('queue_control_dashboard', queue_id=queue_id)

        queue.is_auto_mode_enabled = not queue.is_auto_mode_enabled
        if queue.is_auto_mode_enabled:
            queue.last_auto_served_at = timezone.now()
        queue.save()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'auto_mode_enabled': queue.is_auto_mode_enabled,
                'queue_paused': queue.is_paused,
                'auto_serve_interval': queue.auto_serve_interval,
            })
    return redirect('queue_control_dashboard', queue_id=queue_id)


@staff_member_required
def set_auto_interval(request, queue_id):
    queue = get_object_or_404(Queue, id=queue_id)
    if request.method == 'POST':
        try:
            interval_value = int(request.POST.get('auto_serve_interval'))
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
    served_entries = QueueEntry.objects.filter(
        status='served',
        completed_at__date=today,
        served_at__isnull=False,
        entered_at__isnull=False
    )

    wait_expr = ExpressionWrapper(F('served_at') - F('entered_at'), output_field=DurationField())
    service_expr = ExpressionWrapper(F('completed_at') - F('served_at'), output_field=DurationField())

    aggs = served_entries.aggregate(
        avg_wait=Avg(wait_expr),
        avg_service=Avg(service_expr)
    )

    def minutes(td):
        if not td:
            return None
        try:
            return round(td.total_seconds() / 60.0, 2)
        except Exception:
            return None

    return render(request, 'sqms/staff_reports.html', {
        'today': today,
        'served_today': served_entries.count(),
        'waiting': QueueEntry.objects.filter(status='waiting').count(),
        'skipped': QueueEntry.objects.filter(status='skipped', completed_at__date=today).count(),
        'avg_wait_minutes': minutes(aggs.get('avg_wait')),
        'avg_service_minutes': minutes(aggs.get('avg_service')),
    })


@staff_member_required
def export_reports_pdf(request):
    today = timezone.localdate()
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="report_{today}.pdf"'

    served_entries = QueueEntry.objects.filter(
        status='served',
        completed_at__date=today,
        served_at__isnull=False,
        entered_at__isnull=False
    )

    wait_expr = ExpressionWrapper(F('served_at') - F('entered_at'), output_field=DurationField())
    service_expr = ExpressionWrapper(F('completed_at') - F('served_at'), output_field=DurationField())

    aggs = served_entries.aggregate(
        avg_wait=Avg(wait_expr),
        avg_service=Avg(service_expr)
    )

    def minutes(td):
        if not td:
            return 'N/A'
        try:
            return f"{round(td.total_seconds() / 60.0, 2)} min"
        except Exception:
            return 'N/A'

    data = [
        ['Metric', 'Value'],
        ['Date', str(today)],
        ['Waiting', QueueEntry.objects.filter(status='waiting').count()],
        ['Served Today', served_entries.count()],
        ['Skipped', QueueEntry.objects.filter(status='skipped', completed_at__date=today).count()],
        ['Average Waiting Time', minutes(aggs.get('avg_wait'))],
        ['Average Serving Time', minutes(aggs.get('avg_service'))]
    ]

    table = Table(data)
    table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 1, colors.black)]))

    doc = SimpleDocTemplate(response, pagesize=letter)
    doc.build([Paragraph("Queue Report", styles['Title']), Spacer(1, 20), table])
    return response


@staff_member_required
@require_POST
def send_test_push(request):
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": "Test notification from SQMS"}]
    }
    return JsonResponse(call_groq_api(payload))