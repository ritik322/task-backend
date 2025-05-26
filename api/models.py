from django.db import models
from django.contrib.auth.models import User # Django's built-in User model

class Document(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    # Files will be stored in MEDIA_ROOT/user_documents/
    # MEDIA_ROOT is 'your_project_name/backend/media/'
    file = models.FileField(upload_to='user_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    extracted_text = models.TextField(blank=True, null=True) # To store text from the file

    def __str__(self):
        return f"{self.title} (Uploaded by: {self.user.username})"