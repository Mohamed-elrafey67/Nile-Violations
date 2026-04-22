"""
تحويل ملفات الـ Shapefile إلى JSON جغرافي يستخدمه التطبيق.

الاستخدام:
    python manage.py build_geo_json --shapefile-dir data\\shapefiles\\

المدخلات المطلوبة (في نفس المجلد):
    egy_admbnda_adm3_capmas_20170421.shp
    egy_admbnda_adm3_capmas_20170421.dbf
    egy_admbnda_adm3_capmas_20170421.shx
    egy_admbnda_adm3_capmas_20170421.cpg  (اختياري)

المخرجات:
    data/egypt_adm3_geo.json   ← مضلعات جميع قرى مصر (5716 قرية)
    data/egypt_govs.json       ← بيانات المحافظات الـ 27
"""

import os
import json
import struct
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings


def read_dbf(path):
    """قراءة ملف DBF مع دعم الترميز العربي."""
    with open(path, 'rb') as f:
        f.read(4)
        num_records = struct.unpack('<I', f.read(4))[0]
        header_size = struct.unpack('<H', f.read(2))[0]
        record_size = struct.unpack('<H', f.read(2))[0]
        f.read(20)

        fields = []
        while True:
            fnr = f.read(11)
            if fnr[0:1] == b'\r':
                break
            fn = fnr.replace(b'\x00', b'').decode('ascii', errors='replace')
            ft = f.read(1).decode('ascii')
            f.read(4)
            fl = struct.unpack('B', f.read(1))[0]
            f.read(15)
            fields.append((fn, ft, fl))

        f.seek(header_size)
        records = []
        for _ in range(num_records):
            rec = f.read(record_size)
            if not rec:
                break
            row = {}
            offset = 1
            for fn, ft, fl in fields:
                raw = rec[offset:offset + fl]
                for enc in ['utf-8', 'cp1256', 'latin-1']:
                    try:
                        val = raw.decode(enc).strip()
                        break
                    except Exception:
                        val = raw.decode('latin-1').strip()
                row[fn] = val
                offset += fl
            records.append(row)
    return records


def read_shx_offsets(path):
    """قراءة إزاحات السجلات من ملف SHX."""
    offsets = []
    with open(path, 'rb') as f:
        f.read(100)  # تخطي الترويسة
        while True:
            data = f.read(8)
            if len(data) < 8:
                break
            offsets.append(struct.unpack('>i', data[:4])[0] * 2)
    return offsets


def read_polygon(shp_file, offset, simplify_points=100):
    """
    قراءة مضلع واحد من ملف SHP.
    simplify_points: الحد الأقصى لعدد النقاط في كل حلقة (لتقليل حجم الملف).
    """
    shp_file.seek(offset)
    shp_file.read(8)  # رقم السجل + الطول
    shape_type = struct.unpack('<i', shp_file.read(4))[0]

    if shape_type == 0:
        return None

    # Bounding box
    bbox = struct.unpack('<4d', shp_file.read(32))

    num_parts  = struct.unpack('<i', shp_file.read(4))[0]
    num_points = struct.unpack('<i', shp_file.read(4))[0]
    parts  = [struct.unpack('<i', shp_file.read(4))[0] for _ in range(num_parts)]
    points = [struct.unpack('<2d', shp_file.read(16)) for _ in range(num_points)]

    rings = []
    for i, start in enumerate(parts):
        end  = parts[i + 1] if i + 1 < len(parts) else len(points)
        ring = points[start:end]

        # تبسيط النقاط للأداء على الويب
        step = max(1, len(ring) // simplify_points)
        ring = [[round(p[1], 5), round(p[0], 5)] for p in ring[::step]]

        # إغلاق الحلقة
        if ring and ring[0] != ring[-1]:
            ring.append(ring[0])

        if len(ring) >= 4:  # مضلع صالح
            rings.append(ring)

    if not rings:
        return None

    center = [
        round((bbox[1] + bbox[3]) / 2, 5),
        round((bbox[0] + bbox[2]) / 2, 5),
    ]
    return {'rings': rings, 'center': center}


def find_shapefile(directory):
    """البحث عن ملف .shp في المجلد."""
    for f in os.listdir(directory):
        if f.lower().endswith('.shp'):
            return os.path.join(directory, f[:-4])
    return None


class Command(BaseCommand):
    help = 'تحويل Shapefile إلى JSON جغرافي للتطبيق'

    def add_arguments(self, parser):
        parser.add_argument(
            '--shapefile-dir',
            type=str,
            default=getattr(settings, 'SHAPEFILE_DIR', 'data/shapefiles'),
            help='مجلد يحتوي على ملفات .shp/.dbf/.shx'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default=str(Path(settings.BASE_DIR) / 'data'),
            help='مجلد حفظ ملفات JSON الناتجة'
        )
        parser.add_argument(
            '--simplify',
            type=int,
            default=100,
            help='الحد الأقصى لعدد النقاط في كل مضلع (افتراضي: 100)'
        )
        parser.add_argument(
            '--gov',
            type=str,
            default='',
            help='استخراج محافظة واحدة فقط (مثال: EG12)'
        )

    def handle(self, *args, **options):
        shp_dir    = options['shapefile_dir']
        output_dir = options['output_dir']
        simplify   = options['simplify']
        gov_filter = options['gov']

        # ── التحقق من المجلد ──────────────────────────────────────────────
        if not os.path.isdir(shp_dir):
            self.stdout.write(self.style.ERROR(
                f'✗ المجلد غير موجود: {shp_dir}\n'
                f'  أنشئ المجلد وضع فيه ملفات الـ Shapefile:\n'
                f'  {shp_dir}\\'
                f'egy_admbnda_adm3_capmas_20170421.shp\n'
                f'  {shp_dir}\\'
                f'egy_admbnda_adm3_capmas_20170421.dbf\n'
                f'  {shp_dir}\\'
                f'egy_admbnda_adm3_capmas_20170421.shx'
            ))
            return

        base = find_shapefile(shp_dir)
        if not base:
            self.stdout.write(self.style.ERROR(f'✗ لا يوجد ملف .shp في: {shp_dir}'))
            return

        self.stdout.write(f'📂 الملف: {base}.shp')

        # ── قراءة DBF ─────────────────────────────────────────────────────
        self.stdout.write('⏳ قراءة بيانات الجدول (DBF)...')
        records = read_dbf(base + '.dbf')
        self.stdout.write(f'  ✓ {len(records):,} سجل')

        # ── قراءة SHX ─────────────────────────────────────────────────────
        offsets = read_shx_offsets(base + '.shx')

        # ── استخراج المضلعات ───────────────────────────────────────────────
        self.stdout.write(f'⏳ استخراج المضلعات (تبسيط: {simplify} نقطة)...')
        geo_data = []
        errors   = 0

        with open(base + '.shp', 'rb') as shp:
            for i, rec in enumerate(records):
                gov_pcode = rec.get('ADM1_PCODE', '')

                if gov_filter and gov_pcode != gov_filter:
                    continue

                try:
                    geo = read_polygon(shp, offsets[i], simplify)
                except Exception:
                    errors += 1
                    continue

                if not geo:
                    continue

                geo_data.append({
                    'pcode':          rec.get('ADM3_PCODE', ''),
                    'name_ar':        rec.get('ADM3_AR', ''),
                    'name_en':        rec.get('ADM3_EN', ''),
                    'district_ar':    rec.get('ADM2_AR', ''),
                    'district_en':    rec.get('ADM2_EN', ''),
                    'district_pcode': rec.get('ADM2_PCODE', ''),
                    'gov_ar':         rec.get('ADM1_AR', ''),
                    'gov_en':         rec.get('ADM1_EN', ''),
                    'gov_pcode':      gov_pcode,
                    'center':         geo['center'],
                    'rings':          geo['rings'],
                })

        self.stdout.write(f'  ✓ {len(geo_data):,} مضلع | أخطاء: {errors}')

        # ── بناء بيانات المحافظات ──────────────────────────────────────────
        govs = {}
        for v in geo_data:
            gp = v['gov_pcode']
            if gp not in govs:
                govs[gp] = {
                    'pcode':         gp,
                    'name_ar':       v['gov_ar'],
                    'name_en':       v['gov_en'],
                    'village_count': 0,
                }
            govs[gp]['village_count'] += 1

        # ── حفظ الملفات ───────────────────────────────────────────────────
        os.makedirs(output_dir, exist_ok=True)

        geo_path  = os.path.join(output_dir, 'egypt_adm3_geo.json')
        govs_path = os.path.join(output_dir, 'egypt_govs.json')

        self.stdout.write('💾 حفظ الملفات...')

        with open(geo_path, 'w', encoding='utf-8') as f:
            json.dump(geo_data, f, ensure_ascii=False)
        size_mb = os.path.getsize(geo_path) / 1024 / 1024
        self.stdout.write(f'  ✓ {geo_path}  ({size_mb:.1f} MB)')

        with open(govs_path, 'w', encoding='utf-8') as f:
            json.dump(list(govs.values()), f, ensure_ascii=False)
        self.stdout.write(f'  ✓ {govs_path}')

        # ── ملخص المحافظات ─────────────────────────────────────────────────
        self.stdout.write('\n📊 المحافظات المستخرجة:')
        self.stdout.write(f'  {"الكود":<8} {"الاسم":<25} {"القرى"}')
        self.stdout.write('  ' + '─' * 45)
        for gp, gv in sorted(govs.items()):
            self.stdout.write(f'  {gp:<8} {gv["name_ar"]:<25} {gv["village_count"]:,}')

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ تم بنجاح! {len(geo_data):,} مضلع | {len(govs)} محافظة\n'
            f'   الخطوة التالية:\n'
            f'   python manage.py import_violations "ملف_البيانات.xlsx"'
        ))
