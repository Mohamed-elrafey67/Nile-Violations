import zipfile, os, json
import geopandas as gpd
from django.conf import settings
from django.http import JsonResponse
from .models import Land
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def upload_shapefile(request):
    if request.method == "GET":
        return HttpResponse("""
            <form method="post" enctype="multipart/form-data">
                <input type="file" name="file" required>
                <button type="submit">Upload</button>
            </form>
        """)
    if request.method == "POST":
        file = request.FILES['file']
        path = os.path.join(settings.MEDIA_ROOT, file.name)

        with open(path, 'wb+') as f:
            for chunk in file.chunks():
                f.write(chunk)

        extract_path = path.replace(".zip", "")
        with zipfile.ZipFile(path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        shp_file = None
        for root, dirs, files in os.walk(extract_path):
            for f in files:
                if f.endswith(".shp"):
                    shp_file = os.path.join(root, f)

        if not shp_file:
            return JsonResponse({"error": "No SHP found"})

        gdf = gpd.read_file(shp_file)
        gdf = gdf.to_crs(epsg=4326)

        Land.objects.filter(source_file=file.name).delete()

        for _, row in gdf.iterrows():
            Land.objects.create(
                name=str(row.get('name') or row.get('NAME') or ''),
                area=float(row.get('area') or 0),
                code=str(row.get('code') or ''),
                geometry=json.dumps(row.geometry.__geo_interface__),
                source_file=file.name
            )

        return JsonResponse({"status": "uploaded"})
    return JsonResponse({"error": "invalid"})


def lands_geojson(request):
    features = []
    for land in Land.objects.all():
        features.append({
            "type": "Feature",
            "geometry": json.loads(land.geometry),
            "properties": {
                "name": land.name,
                "area": land.area,
                "code": land.code
            }
        })
    return JsonResponse({"type": "FeatureCollection", "features": features})
