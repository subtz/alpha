from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calc', '0007_queue_current_ticket_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='queue',
            name='auto_mode',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='queue',
            name='auto_serve_interval',
            field=models.PositiveIntegerField(default=5, help_text='Auto serve interval in minutes'),
        ),
    ]
