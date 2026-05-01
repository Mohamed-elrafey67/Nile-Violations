from django.db import models

class Land(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    area = models.FloatField(null=True, blank=True)
    code = models.CharField(max_length=100, null=True, blank=True)
    geometry = models.TextField()
    source_file = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
