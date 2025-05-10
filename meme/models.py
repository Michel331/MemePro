from django.db import models

# Create your models here.

class Meme(models.Model):
    original_image = models.ImageField(upload_to='originals/')
    top_text = models.CharField(max_length=100, blank=True)
    bottom_text = models.CharField(max_length=100, blank=True)
    generated_image = models.ImageField(upload_to='generated/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Meme {self.id} - {self.created_at}"
