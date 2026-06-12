# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class ValidStudent(models.Model):

    YEAR_CHOICES = [
        (1, 'Year 1'),
        (2, 'Year 2'),
        (3, 'Year 3'),
        (4, 'Year 4'),
    ]

    registration_number = models.CharField(
        max_length=13,
        unique=True
    )

    full_name = models.CharField(
        max_length=100
    )

    year_of_study = models.IntegerField(
        choices=YEAR_CHOICES
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):

        return f"{self.registration_number} - {self.full_name}"

    class Meta:

        verbose_name = "Valid Student"

        verbose_name_plural = "Valid Students"


class StudentProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='student_profile'
    )

    valid_student = models.ForeignKey(
        ValidStudent,
        on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):

        return f"{self.user.username} - {self.valid_student.registration_number}"

    class Meta:

        verbose_name = "Student Profile"

        verbose_name_plural = "Student Profiles"


class Queue(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    description = models.TextField(
        blank=True
    )

    allowed_years = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Comma-separated allowed years, e.g. 1,2,3,4"
    )

    is_active = models.BooleanField(
        default=True
    )

    is_paused = models.BooleanField(
        default=False
    )

    max_capacity = models.PositiveIntegerField(
        default=50
    )

    current_ticket_number = models.PositiveIntegerField(
        default=0
    )

    is_auto_mode_enabled = models.BooleanField(
        default=False
    )

    auto_serve_interval = models.PositiveIntegerField(
        default=0,
        help_text="Auto serve interval in minutes"
    )

    last_auto_served_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):

        return self.name

    class Meta:

        verbose_name = "Queue"

        verbose_name_plural = "Queues"


class Customer(models.Model):

    name = models.CharField(
        max_length=255
    )

    email = models.EmailField(
        unique=True
    )

    phone = models.CharField(
        max_length=20,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):

        return f"{self.name} ({self.email})"

    class Meta:

        verbose_name = "Customer"

        verbose_name_plural = "Customers"


class Service(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    description = models.TextField(
        blank=True
    )

    estimated_time = models.PositiveIntegerField(
        default=5,
        help_text="Estimated service time in minutes"
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):

        return self.name

    class Meta:

        verbose_name = "Service"

        verbose_name_plural = "Services"


class QueueEntry(models.Model):

    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('serving', 'Serving'),
        ('served', 'Served'),
        ('skipped', 'Skipped'),
    ]

    queue = models.ForeignKey(
        Queue,
        on_delete=models.CASCADE
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE
    )

    position = models.PositiveIntegerField()

    ticket_number = models.CharField(
        max_length=20,
        blank=True,
        editable=False
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='waiting'
    )

    entered_at = models.DateTimeField(
        auto_now_add=True
    )

    served_at = models.DateTimeField(
        null=True,
        blank=True
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    notes = models.TextField(
        blank=True
    )

    def save(self, *args, **kwargs):
        if self.position and not self.ticket_number:
            self.ticket_number = f"SC-{self.position:03d}"
        super().save(*args, **kwargs)

    def __str__(self):

        return f"{self.ticket_number} - {self.customer.name}"

    class Meta:

        verbose_name = "Queue Entry"

        verbose_name_plural = "Queue Entries"

        unique_together = ('queue', 'position')

        ordering = ['position']

    def clean(self):

        if self.status in ['serving', 'served'] and not self.served_at:

            raise ValidationError(
                "Served time must be set when status is serving or served."
            )

        if self.status == 'served' and not self.completed_at:

            raise ValidationError(
                "Completed time must be set when status is served."
            )

        super().clean()


class PushSubscription(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='push_subscriptions'
    )

    endpoint = models.CharField(max_length=500)
    p256dh = models.CharField(max_length=255, blank=True)
    auth_key = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Push Subscription'
        verbose_name_plural = 'Push Subscriptions'
        unique_together = ('user', 'endpoint')

    def __str__(self):
        return f"PushSubscription for {self.user.username} - {self.endpoint[:50]}"


class NotificationLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notification_logs'
    )
    email = models.EmailField()
    message_text = models.TextField()
    success = models.BooleanField(default=False)
    error = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"
        ordering = ['-timestamp']

    def __str__(self):
        return f"Log to {self.email} - {'Success' if self.success else 'Failure'} at {self.timestamp}"