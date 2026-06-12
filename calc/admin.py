from django.contrib import admin, messages
from django.utils import timezone
from datetime import timedelta
from .models import Queue, Customer, Service, QueueEntry, ValidStudent, StudentProfile, PushSubscription

# Register your models here.
admin.site.register(Queue)
admin.site.register(Customer)
admin.site.register(Service)
admin.site.register(QueueEntry)
admin.site.register(ValidStudent)
admin.site.register(StudentProfile)


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
	list_display = ('user', 'endpoint', 'created_at')
	search_fields = ('user__username', 'endpoint')

	@admin.action(description='Delete push subscriptions older than 90 days')
	def delete_old_subscriptions(self, request, queryset):
		cutoff = timezone.now() - timedelta(days=90)
		old_qs = self.model.objects.filter(created_at__lt=cutoff)
		count = old_qs.count()
		old_qs.delete()
		self.message_user(request, f'Deleted {count} push subscriptions older than 90 days.', level=messages.SUCCESS)

	actions = ['delete_old_subscriptions']
