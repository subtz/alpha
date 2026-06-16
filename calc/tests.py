from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from calc.models import PushSubscription, NotificationLog, Queue, QueueEntry, Customer, Service
from calc.views import send_student_notification, advance_queue
from django.utils import timezone
import json
from unittest.mock import patch

class SQMSNotificationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='teststudent', email='student@example.com', password='password123')
        self.customer = Customer.objects.create(name='teststudent', email='student@example.com')
        self.service = Service.objects.create(name='Academic Advising', estimated_time=15)
        self.queue = Queue.objects.create(name='Advising Queue', description='Queue for advising')

    def test_push_subscription_model_saving(self):
        sub = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://fcm.googleapis.com/fcm/send/some-token',
            p256dh='test-p256dh',
            auth_key='test-auth-key'
        )
        self.assertEqual(sub.user, self.user)
        self.assertEqual(sub.endpoint, 'https://fcm.googleapis.com/fcm/send/some-token')
        self.assertEqual(sub.p256dh, 'test-p256dh')
        self.assertEqual(sub.auth_key, 'test-auth-key')

    def test_save_push_subscription_endpoint(self):
        self.client.login(username='teststudent', password='password123')
        url = reverse('push_subscribe')
        
        payload = {
            'subscription': {
                'endpoint': 'https://updates.push.services.mozilla.com/push/v1/gAAAAA',
                'keys': {
                    'p256dh': 'p256dh_value',
                    'auth': 'auth_value'
                }
            }
        }
        
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(data['created'])
        
        # Verify saved in db
        sub = PushSubscription.objects.get(user=self.user)
        self.assertEqual(sub.endpoint, 'https://updates.push.services.mozilla.com/push/v1/gAAAAA')
        self.assertEqual(sub.p256dh, 'p256dh_value')
        self.assertEqual(sub.auth_key, 'auth_value')

    @patch('calc.views.webpush')
    def test_send_student_notification_success(self, mock_webpush):
        # Create subscription
        PushSubscription.objects.create(
            user=self.user,
            endpoint='https://endpoint.com',
            p256dh='p256dh',
            auth_key='auth'
        )
        
        # QueueEntry
        entry = QueueEntry.objects.create(
            queue=self.queue,
            customer=self.customer,
            service=self.service,
            position=1,
            status='waiting'
        )
        
        res = send_student_notification(entry, "Test notification message")
        self.assertTrue(res['success'])
        
        # Verify log
        log = NotificationLog.objects.get(user=self.user)
        self.assertTrue(log.success)
        self.assertEqual(log.message_text, "Test notification message")
        self.assertEqual(log.error, "")

    @patch('calc.views.webpush')
    def test_send_student_notification_failure(self, mock_webpush):
        from pywebpush import WebPushException
        mock_webpush.side_effect = WebPushException("Push failed completely")
        
        # Create subscription
        PushSubscription.objects.create(
            user=self.user,
            endpoint='https://endpoint.com',
            p256dh='p256dh',
            auth_key='auth'
        )
        
        entry = QueueEntry.objects.create(
            queue=self.queue,
            customer=self.customer,
            service=self.service,
            position=1,
            status='waiting'
        )
        
        res = send_student_notification(entry, "Fail message")
        self.assertFalse(res['success'])
        
        # Verify log
        log = NotificationLog.objects.get(user=self.user)
        self.assertFalse(log.success)
        self.assertEqual(log.message_text, "Fail message")
        self.assertEqual(log.error, "Push failed")

    @patch('calc.views.webpush')
    def test_advance_queue(self, mock_webpush):
        # Setup 4 customers/entries in queue
        customers = []
        entries = []
        for i in range(1, 5):
            u = User.objects.create_user(username=f'student{i}', email=f'student{i}@example.com', password='pass')
            # create subscription so notifications don't short-circuit or can actually log success
            PushSubscription.objects.create(user=u, endpoint=f'https://end{i}.com', p256dh='p', auth_key='a')
            c = Customer.objects.create(name=f'student{i}', email=f'student{i}@example.com')
            entry = QueueEntry.objects.create(
                queue=self.queue,
                customer=c,
                service=self.service,
                position=i,
                status='waiting'
            )
            customers.append(c)
            entries.append(entry)
            
        # Initially let's mark entry 1 as serving
        entries[0].status = 'serving'
        entries[0].served_at = timezone.now()
        entries[0].save()
        
        # Advance queue
        advance_queue(self.queue.id)
        
        # 1. Current entry (entry 1) moves to 'served'
        entry1 = QueueEntry.objects.get(id=entries[0].id)
        self.assertEqual(entry1.status, 'served')
        self.assertIsNotNone(entry1.completed_at)
        
        # 2. Next entry (entry 2) moves to 'serving'
        entry2 = QueueEntry.objects.get(id=entries[1].id)
        self.assertEqual(entry2.status, 'serving')
        self.assertIsNotNone(entry2.served_at)
        
        # Verify logs
        u2 = User.objects.get(email=entry2.customer.email)
        log2 = NotificationLog.objects.filter(user=u2).first()
        self.assertIn("It's your turn!", log2.message_text)
        
        u3 = User.objects.get(email=entries[2].customer.email)
        log3 = NotificationLog.objects.filter(user=u3).first()
        self.assertIn("You are next in line!", log3.message_text)
        
        u4 = User.objects.get(email=entries[3].customer.email)
        log4 = NotificationLog.objects.filter(user=u4).first()
        self.assertIsNone(log4) # No notification because tickets_ahead is 1
