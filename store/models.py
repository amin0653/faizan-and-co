from django.db import models

class Product(models.Model):
    title = models.CharField(max_length=200)
    image_url = models.URLField(blank=True, null=True)
    image_upload = models.ImageField(upload_to='products/', blank=True, null=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    original_link = models.URLField()
    seller_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
    @property
    def get_image(self):
        """Returns uploaded image or URL image"""
        if self.image_upload:
            return self.image_upload.url
        elif self.image_url:
            return self.image_url
        return None

class ContactMessage(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    subject = models.CharField(max_length=300)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Message from {self.name} - {self.subject}"