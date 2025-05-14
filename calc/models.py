
# Create your models here.
from django.db import models
from django.contrib.auth.models import User

# Model to store uploaded handwritten documents
class DocumentUpload(models.Model):
    # Link each upload to the logged-in user
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    customer_name = models.CharField(max_length=255)  # Name shown on the document
    original_file = models.FileField(upload_to='uploads/original/')  # Where the file is saved
    uploaded_at = models.DateTimeField(auto_now_add=True)  # Timestamp of upload
    status = models.CharField(
        max_length=50,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('converted', 'Converted'),
            ('failed', 'Failed')
        ],
        default='pending'
    )

    def __str__(self):
        return f"{self.customer_name} - {self.status}"

# Model for storing the processed version of the uploaded file
class ProcessedDocument(models.Model):
    document = models.OneToOneField(DocumentUpload, on_delete=models.CASCADE)
    converted_file = models.FileField(upload_to='uploads/converted/', null=True, blank=True)
    drive_link = models.URLField(blank=True, null=True)  # Shareable Google Drive link
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Processed: {self.document.customer_name}"

# Model to store loss reports and their payment status
class LossReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Owner of the report
    customer_name = models.CharField(max_length=255)
    control_number = models.CharField(max_length=100)  # From external system
    payment_confirmed = models.BooleanField(default=False)  # After verifying with payment provider
    report_file = models.FileField(upload_to='loss_reports/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Loss Report - {self.customer_name} | Paid: {self.payment_confirmed}"
