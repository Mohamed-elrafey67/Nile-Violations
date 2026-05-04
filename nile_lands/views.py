from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Q
from django.http import JsonResponse

from .models import LandParcel


@login_required(login_url='login')
def map_view(request):
    govs = (
        LandParcel.objects
        .values_list('governorate', flat=True)
        .distinct()
        .order_by('governorate')
    )

    total_count = LandParcel.objects.count()
    total_area = sum(float(x.area or 0) for x in LandParcel.objects.only('area'))

    context = {
        'user': request.user,
        'system_name': 'منظومة اراضي طرح النيل',

        # لتغذية القائمة المنسدلة الحالية
        'govs_with_data': [{'name_ar': g} for g in govs],

        # للحفاظ على مؤشرات الرأس الحالية
        'overall': {
            'total_count': total_count,
            'total_area': round(total_area, 2),
            'geo_count': total_count,
        }
    }

    return render(request, 'nile_lands/map.html', context)

@login_required(login_url='login')
def parcels_api(request):
    qs = LandParcel.objects.all()

    gov = request.GET.get('gov', '').strip()
    district = request.GET.get('district', '').strip()
    village = request.GET.get('village', '').strip()
    search = request.GET.get('search', '').strip()
    min_area = request.GET.get('min_area', '').strip()

    if gov:
        qs = qs.filter(governorate=gov)

    if district:
        qs = qs.filter(district=district)

    if village:
        qs = qs.filter(village=village)

    if search:
        qs = qs.filter(
            Q(exploiter_name__icontains=search) |
            Q(symbol__icontains=search) |
            Q(parcel_id__icontains=search) |
            Q(basin_name__icontains=search)
        )

    if min_area:
        try:
            qs = qs.filter(area__gte=float(min_area))
        except Exception:
            pass

    total_count = qs.count()
    total_area = sum(float(x.area or 0) for x in qs[:3000])

    features = []

    for p in qs[:3000]:
        if not p.geometry:
            continue

        features.append({
            "type": "Feature",
            "geometry": p.geometry,
            "properties": {
                "id": p.id,
                "symbol": p.symbol,
                "governorate": p.governorate,
                "district": p.district,
                "village": p.village,
                "exploiter_name": p.exploiter_name,
                "basin_name": p.basin_name,
                "area": float(p.area or 0),
                "remarks": p.remarks,
            }
        })

    return JsonResponse({
        "type": "FeatureCollection",
        "features": features,
        "count": total_count,
        "total_area": round(total_area, 2),
    })

@login_required(login_url='login')
def parcel_detail_api(request, pk):
    p = LandParcel.objects.get(pk=pk)

    return JsonResponse({
        "id": p.id,
        "symbol": p.symbol,
        "parcel_id": p.parcel_id,
        "governorate": p.governorate,
        "district": p.district,
        "village": p.village,
        "exploiter_name": p.exploiter_name,
        "basin_name": p.basin_name,
        "area": p.area,
        "remarks": p.remarks,
    })

@login_required(login_url='login')
def parcels_geojson(request):
    qs = LandParcel.objects.all()

    gov = request.GET.get('gov', '').strip()
    district = request.GET.get('district', '').strip()
    village = request.GET.get('village', '').strip()
    search = request.GET.get('search', '').strip()
    min_area = request.GET.get('min_area', '').strip()

    if gov:
        qs = qs.filter(governorate=gov)

    if district:
        qs = qs.filter(district=district)

    if village:
        qs = qs.filter(village=village)

    if search:
        qs = qs.filter(
            Q(exploiter_name__icontains=search) |
            Q(symbol__icontains=search) |
            Q(parcel_id__icontains=search) |
            Q(basin_name__icontains=search)
        )

    if min_area:
        try:
            qs = qs.filter(area__gte=float(min_area))
        except Exception:
            pass

    features = []

    for p in qs[:3000]:
        if not p.geometry:
            continue

        features.append({
            "type": "Feature",
            "geometry": p.geometry,
            "properties": {
                "id": p.id,
                "symbol": p.symbol,
                "governorate": p.governorate,
                "district": p.district,
                "village": p.village,
                "exploiter_name": p.exploiter_name,
                "basin_name": p.basin_name,
                "area": float(p.area or 0),
                "remarks": p.remarks,
            }
        })

    total_area = sum(float(p.area or 0) for p in qs[:3000])

    return JsonResponse({
        "type": "FeatureCollection",
        "features": features,
        "count": qs.count(),
        "total_area": round(total_area, 2),
    })


@login_required(login_url='login')
def parcel_filter_options(request):
    gov = request.GET.get('gov', '').strip()
    district = request.GET.get('district', '').strip()

    qs = LandParcel.objects.all()

    governorates = sorted(
        qs.values_list('governorate', flat=True).distinct()
    )

    districts = []
    villages = []

    if gov:
        districts = sorted(
            qs.filter(governorate=gov)
              .values_list('district', flat=True)
              .distinct()
        )

    if gov and district:
        villages = sorted(
            qs.filter(governorate=gov, district=district)
              .values_list('village', flat=True)
              .distinct()
        )

    return JsonResponse({
        "governorates": list(governorates),
        "districts": list(districts),
        "villages": list(villages),
    })