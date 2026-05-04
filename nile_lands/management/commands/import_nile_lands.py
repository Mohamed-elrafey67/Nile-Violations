import zipfile
import tempfile
from pathlib import Path

import geopandas as gpd

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from nile_lands.models import DatasetVersion, LandParcel


class Command(BaseCommand):
    help = "استيراد ملف shapefile لأراضي طرح النيل"

    def add_arguments(self, parser):
        parser.add_argument("zip_path", type=str)
        parser.add_argument("--name", type=str, default="طبقة أراضي طرح النيل")
        parser.add_argument("--description", type=str, default="")

    def handle(self, *args, **options):
        zip_path = Path(options["zip_path"])

        if not zip_path.exists():
            self.stderr.write("الملف غير موجود")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmpdir)

            shp_files = list(Path(tmpdir).rglob("*.shp"))

            if not shp_files:
                self.stderr.write("لم يتم العثور على shapefile")
                return

            shp_path = shp_files[0]

            gdf = gpd.read_file(shp_path)

            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:32636")

            gdf = gdf.to_crs("EPSG:4326")

            dataset = DatasetVersion.objects.create(
                name=options["name"],
                description=options["description"],
                uploaded_by=None,
                is_active=True,
            )

            created = 0

            for _, row in gdf.iterrows():
                geom = row.geometry.__geo_interface__ if row.geometry else None

                LandParcel.objects.create(
                    dataset=dataset,
                    symbol=str(row.get("Symbol", "") or ""),
                    parcel_id=str(row.get("ID", "") or ""),
                    governorate=str(row.get("EpoName", "") or ""),
                    district=str(row.get("EdoName", "") or ""),
                    village=str(row.get("VillageNam", "") or ""),
                    exploiter_name=str(row.get("NameInFiel", "") or ""),
                    basin_name=str(row.get("HodName", "") or ""),
                    area=float(row.get("AreaOutsid", 0) or 0),
                    remarks=str(row.get("Remarks", "") or ""),
                    geometry=geom,
                )

                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"تم استيراد {created} قطعة أرض"
            )
        )