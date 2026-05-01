from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_shapefile),
    path('geojson/', views.lands_geojson),
]
