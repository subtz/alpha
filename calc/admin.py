from django.contrib import admin
from .models import Queue, Customer, Service, QueueEntry, ValidStudent, StudentProfile

# Register your models here.
admin.site.register(Queue)
admin.site.register(Customer)
admin.site.register(Service)
admin.site.register(QueueEntry)
admin.site.register(ValidStudent)
admin.site.register(StudentProfile)
