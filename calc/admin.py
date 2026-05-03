from django.contrib import admin
from .models import Queue, Customer, Service, QueueEntry

# Register your models here.
admin.site.register(Queue)
admin.site.register(Customer)
admin.site.register(Service)
admin.site.register(QueueEntry)
