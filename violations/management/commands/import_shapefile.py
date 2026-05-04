import os
import zipfile
import tempfile
import shutil
import json
from pathlib import Path

import fiona
from django.core.management.base import BaseCommand
from django.db import transaction

from violations.models import LandParcel


class Command(BaseCommand):
    help = 'استيراد ملف Shapefile مضغوط لمحافظة (متوافق مع SQLite3)'

    def add_arguments(self, parser):
        parser.add_argument('zipfile', type=str, help='مسار ملف ZIP')
        parser.add_argument('--gov-code', type=str, required=True, help='كود المحافظة (مثال: EG12)')
        parser.add_argument('--gov-name', type=str, required=True, help='اسم المحافظة')
        parser.add_argument('--dry-run', action='store_true', help='تجربة بدون حفظ')
        parser.add_argument('--clear-gov', action='store_true', help='حذف بيانات المحافظة القديمة')
        parser.add_argument('--encoding', type=str, default='utf-8', help='ترميز ملف DBF')

    def handle(self, *args, **options):
        zip_path = options['zipfile']
        gov_code = options['gov_code']
        gov_name = options['gov_name']
        dry_run = options['dry_run']
        clear_gov = options['clear_gov']
        encoding = options['encoding']

        if not os.path.exists(zip_path):
            self.stderr.write(self.style.ERROR(f"الملف غير موجود: {zip_path}"))
            return

        # فك الضغط
        temp_dir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(temp_dir)

            # البحث عن ملف .shp
            shp_files = list(Path(temp_dir).rglob('*.shp'))
            if not shp_files:
                self.stderr.write(self.style.ERROR("لم يُعثر على ملف .shp في الأرشيف"))
                return

            shp_path = str(shp_files[0])
            self.stdout.write(self.style.SUCCESS(f"تم العثور على: {os.path.basename(shp_path)}"))

            # فحص البيانات
            parcels_data = []
            total_records = 0

            with fiona.open(shp_path, encoding=encoding) as src:
                total_records = len(src)
                self.stdout.write(f"إجمالي المعالم: {total_records}")
                self.stdout.write(f"نظام الإحداثيات الأصلي: {src.crs}")
                self.stdout.write(f"الحقول المتاحة: {list(src.schema['properties'].keys())}")

                for feat in src:
                    geom = feat.geometry
                    props = feat.properties

                    # تحويل الإحداثيات من EPSG:22992 إلى EPSG:4326
                    # باستخدام pyproj (أو fiona تلقائياً)
                    geom_dict = self._transform_geometry(geom)

                    # حساب مركز المضلع
                    center = self._calculate_center(geom_dict)

                    # استخراج البيانات مع معالجة القيم الفارغة
                    parcel_data = {
                        'parcel_id': self._safe_int(props.get('ID')),
                        'symbol': self._safe_str(props.get('Symbol')),
                        'governorate': self._safe_str(props.get('EpoName')) or gov_name,
                        'center': self._safe_str(props.get('EdoName')),
                        'village': self._safe_str(props.get('VillageNam')),
                        'basin': self._safe_str(props.get('HodName')) or self._safe_str(props.get('ZoneName')),
                        'bank': self._safe_str(props.get('Bank')),
                        'beneficiary': self._safe_str(props.get('NameInFiel')),
                        'beneficiary_new': self._safe_str(props.get('NewNameInF')),
                        'declared_name': self._safe_str(props.get('NameStated')),

                        # نوع الاستغلال من حقل Remarks
                        'usage_description': self._safe_str(props.get('Remarks')),

                        # المساحات
                        'area_inside': self._safe_float(props.get('AreaInside')),
                        'area_outside': self._safe_float(props.get('AreaOutsid')),
                        'area_public': self._safe_float(props.get('InfrAreaPu')),
                        'area_bridge': self._safe_float(props.get('InfrAreaNi')),
                        'area_shore': self._safe_float(props.get('InfrAreaSh')),
                        'area_street': self._safe_float(props.get('InfrAreaSt')),
                        'area_backfill_1982': self._safe_float(props.get('AreaBackFi')),
                        'area_backfill_2003': self._safe_float(props.get('AreaBack_1')),
                        'area_backfill_other': self._safe_float(props.get('AreaBack_2')),
                        'area_backfill_3': self._safe_float(props.get('AreaBack_3')),
                        'building_area': self._safe_float(props.get('BuildingAr')),

                        # المحاضر
                        'first_contract_no': self._safe_str(props.get('FristContr')),
                        'first_contract_area': self._safe_str(props.get('AreaOfFris')),
                        'second_contract_no': self._safe_str(props.get('SecondCont')),
                        'second_contract_area': self._safe_str(props.get('AreaOfSeco')),
                        'third_contract_no': self._safe_str(props.get('ThirdContr')),
                        'third_contract_area': self._safe_str(props.get('AreaOfThir')),
                        'fourth_contract_no': self._safe_str(props.get('FourthCont')),
                        'fourth_contract_area': self._safe_str(props.get('AreaOfFour')),
                        'fifth_contract_no': self._safe_str(props.get('FifthContr')),
                        'fifth_contract_area': self._safe_str(props.get('AreaOfFift')),

                        # المساحات المستردة
                        'area_lost_1': self._safe_str(props.get('AreaOfLost')),
                        'area_lost_2': self._safe_str(props.get('AreaOfLo_1')),

                        # الحالات
                        'status': self._safe_str(props.get('Status')),
                        'repeat_service': self._safe_str(props.get('RepeatServ')),
                        'other_cases': self._safe_str(props.get('OtherCase')),
                        'building_status': self._safe_str(props.get('BuildingSt')),
                        'ownership_status': self._safe_str(props.get('OwnerShipS')),

                        # الاستمارات
                        'request_number': self._safe_str(props.get('RequstNumb')),
                        'form_number': self._safe_str(props.get('EstmarahNu')),
                        'form_area': self._safe_str(props.get('AreaOfEstm')),

                        # الملاحظات
                        'notes_print': self._safe_str(props.get('NotsForPri')),
                        'notes_edit': self._safe_str(props.get('NotsOfEdit')),

                        # البيانات المكانية (مخزنة كـ GeoJSON نصي)
                        'geojson': json.dumps(geom_dict),
                        'center_lat': center['lat'],
                        'center_lng': center['lng'],

                        # البيانات الوصفية
                        'source_file': os.path.basename(zip_path),
                    }
                    parcels_data.append(parcel_data)

            if dry_run:
                self.stdout.write(self.style.WARNING("═" * 60))
                self.stdout.write(self.style.WARNING("وضع التجربة - لن يتم الحفظ في قاعدة البيانات"))
                self.stdout.write(self.style.WARNING("═" * 60))
                self.stdout.write(f"
إجمالي السجلات المُحللة: {len(parcels_data)}")
                self.stdout.write("
أول 5 سجلات:")
                for p in parcels_data[:5]:
                    self.stdout.write(f"  • {p['symbol']} | {p['village']} | {p['beneficiary']} | {p['usage_description']}")

                # إحصائيات سريعة
                self.stdout.write("
📊 إحصائيات:")
                gov_count = len(set(p['governorate'] for p in parcels_data))
                center_count = len(set(p['center'] for p in parcels_data if p['center']))
                village_count = len(set(p['village'] for p in parcels_data if p['village']))
                self.stdout.write(f"   المحافظات: {gov_count}")
                self.stdout.write(f"   المراكز: {center_count}")
                self.stdout.write(f"   القرى: {village_count}")
                return

            # الحفظ في قاعدة البيانات
            with transaction.atomic():
                if clear_gov:
                    deleted, _ = LandParcel.objects.filter(
                        governorate__icontains=gov_name
                    ).delete()
                    self.stdout.write(self.style.WARNING(f"تم حذف {deleted} سجل قديم"))

                created = 0
                updated = 0
                errors = 0

                for data in parcels_data:
                    try:
                        parcel, was_created = LandParcel.objects.update_or_create(
                            parcel_id=data['parcel_id'],
                            defaults=data
                        )
                        if was_created:
                            created += 1
                        else:
                            updated += 1
                    except Exception as e:
                        errors += 1
                        self.stderr.write(self.style.ERROR(
                            f"خطأ في سجل {data.get('symbol', 'N/A')}: {str(e)}"
                        ))

                self.stdout.write(self.style.SUCCESS("═" * 60))
                self.stdout.write(self.style.SUCCESS(f"✅ تم استيراد بيانات {gov_name} بنجاح!"))
                self.stdout.write(self.style.SUCCESS("═" * 60))
                self.stdout.write(f"   جديد: {created}")
                self.stdout.write(f"   مُحدَّث: {updated}")
                self.stdout.write(f"   أخطاء: {errors}")
                self.stdout.write(f"   الإجمالي: {created + updated}")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _transform_geometry(self, geom):
        """تحويل الإحداثيات من EPSG:22992 إلى EPSG:4326"""
        try:
            from pyproj import Transformer
            transformer = Transformer.from_crs("EPSG:22992", "EPSG:4326", always_xy=True)

            coords = geom['coordinates']
            geom_type = geom['type']

            if geom_type == 'Polygon':
                new_coords = []
                for ring in coords:
                    new_ring = []
                    for x, y in ring:
                        lng, lat = transformer.transform(x, y)
                        new_ring.append([lng, lat])
                    new_coords.append(new_ring)
                return {'type': 'Polygon', 'coordinates': new_coords}

            elif geom_type == 'MultiPolygon':
                new_coords = []
                for polygon in coords:
                    new_poly = []
                    for ring in polygon:
                        new_ring = []
                        for x, y in ring:
                            lng, lat = transformer.transform(x, y)
                            new_ring.append([lng, lat])
                        new_poly.append(new_ring)
                    new_coords.append(new_poly)
                return {'type': 'MultiPolygon', 'coordinates': new_coords}

            return geom
        except ImportError:
            self.stdout.write(self.style.WARNING("pyproj غير مُثبت، سيتم استخدام الإحداثيات الأصلية"))
            return geom

    def _calculate_center(self, geom_dict):
        """حساب مركز المضلع"""
        try:
            coords = geom_dict['coordinates']
            geom_type = geom_dict['type']

            if geom_type == 'Polygon':
                # أول ring (الخارجي)
                ring = coords[0]
                lats = [p[1] for p in ring]
                lngs = [p[0] for p in ring]
                return {'lat': sum(lats) / len(lats), 'lng': sum(lngs) / len(lngs)}

            elif geom_type == 'MultiPolygon':
                # أول polygon، أول ring
                ring = coords[0][0]
                lats = [p[1] for p in ring]
                lngs = [p[0] for p in ring]
                return {'lat': sum(lats) / len(lats), 'lng': sum(lngs) / len(lngs)}

            return {'lat': None, 'lng': None}
        except:
            return {'lat': None, 'lng': None}

    def _safe_str(self, value):
        """تحويل قيمة آمنة إلى نص"""
        if value is None or value == '' or value == 'None':
            return None
        return str(value).strip()

    def _safe_float(self, value):
        """تحويل قيمة آمنة إلى float"""
        if value is None or value == '' or value == 'None':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value):
        """تحويل قيمة آمنة إلى int"""
        if value is None or value == '' or value == 'None':
            return 0
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0
