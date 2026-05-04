from django.urls import path
from . import views

urlpatterns = [
    path('', views.map_view, name='nile_lands_map'),
    path('api/parcels/', views.parcels_api, name='nile_lands_parcels_api'),
    path('api/parcels/<int:pk>/', views.parcel_detail_api, name='nile_lands_parcel_detail'),
    path('api/filter-options/', views.parcel_filter_options, name='nile_lands_filter_options'),
]