from django.db import models
from django.contrib.auth.models import User


class DatasetVersion(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    data_date = models.DateField(null=True, blank=True)

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class LandParcel(models.Model):
    dataset = models.ForeignKey(
        DatasetVersion,
        on_delete=models.CASCADE,
        related_name='parcels'
    )

    symbol = models.CharField(max_length=120, blank=True)
    parcel_id = models.CharField(max_length=120, blank=True)

    governorate = models.CharField(max_length=150, db_index=True)
    district = models.CharField(max_length=150, db_index=True)
    village = models.CharField(max_length=150, db_index=True)

    exploiter_name = models.CharField(max_length=255, blank=True)
    basin_name = models.CharField(max_length=255, blank=True)

    area = models.FloatField(default=0)

    remarks = models.TextField(blank=True)

    geometry = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.symbol} - {self.village}'


class UserGeoPermission(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='land_permissions'
    )

    governorate = models.CharField(max_length=150, blank=True)
    district = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return f'{self.user.username}'