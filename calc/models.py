
# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class Queue(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_paused = models.BooleanField(default=False)
    max_capacity = models.PositiveIntegerField(default=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Queue"
        verbose_name_plural = "Queues"

class Customer(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.email})"

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

class Service(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    estimated_time = models.PositiveIntegerField(help_text="Estimated service time in minutes")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"

class QueueEntry(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('serving', 'Serving'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
    ]

    queue = models.ForeignKey(Queue, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    created_at = models.DateTimeField(auto_now_add=True)
    entered_at = models.DateTimeField(auto_now_add=True)
    served_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def ticket_number(self):
        return f"SC-{self.position:03d}"

    def __str__(self):
        return f"{self.ticket_number()} - {self.customer.name}"

    class Meta:
        verbose_name = "Queue Entry"
        verbose_name_plural = "Queue Entries"
        unique_together = ('queue', 'position')

    def clean(self):
        if self.status in ['serving', 'completed'] and not self.served_at:
            raise ValidationError("Served time must be set when status is serving or completed.")
        if self.status == 'completed' and not self.completed_at:
            raise ValidationError("Completed time must be set when status is completed.")
        super().clean()
