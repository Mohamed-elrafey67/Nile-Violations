"""
استيراد بيانات التعديات من ملف Excel مع ربطها بالخرائط الجغرافية.

يعمل مع أي محافظة مصرية — يكتشف المحافظة تلقائياً من البيانات.

الاستخدام:
    # استيراد الدقهلية مع الشيب فايل:
    python manage.py import_violations data/الدقهلية.xlsx \\
        --geo-json data/egypt_adm3_geo.json

    # استيراد بدون خرائط (احتياطي بالإحداثيات التقديرية):
    python manage.py import_violations data/الدقهلية.xlsx

    # استيراد عدة محافظات دفعة واحدة:
    python manage.py import_violations data/*.xlsx --geo-json data/egypt_adm3_geo.json

    # مسح بيانات محافظة معينة قبل إعادة الاستيراد:
    python manage.py import_violations data/الدقهلية.xlsx --clear-gov EG12
"""

import os
import re
import json
import random
import glob
from django.core.management.base import BaseCommand
from django.conf import settings
import pandas as pd
from violations.models import Violation, Governorate, District


# ── إحداثيات عواصم المحافظات (احتياطي إذا لم يوجد شيب فايل) ─────────────
GOV_CENTERS = {
    'القاهرة':         (30.0444, 31.2357), 'الاسكندرية':    (31.2001, 29.9187),
    'بورسعيد':         (31.2565, 32.2841), 'السويس':        (29.9668, 32.5498),
    'دمياط':           (31.4165, 31.8133), 'الدقهلية':      (31.0361, 31.3807),
    'الشرقية':         (30.7444, 31.6638), 'القليوبية':     (30.3292, 31.2192),
    'كفر الشيخ':       (31.1107, 30.9388), 'الغربية':       (30.8748, 31.0326),
    'المنوفية':        (30.5973, 30.9876), 'البحيرة':       (30.8480, 30.3446),
    'الإسماعيلية':     (30.5965, 32.2715), 'الجيزة':        (29.9870, 31.2118),
    'بنى سويف':        (29.0661, 31.0994), 'الفيوم':        (29.3084, 30.8428),
    'المنيا':          (28.0871, 30.7618), 'أسيوط':         (27.1794, 31.1837),
    'سوهاج':           (26.5569, 31.6948), 'قنا':           (26.1551, 32.7160),
    'أسوان':           (24.0889, 32.8998), 'مدينة الأقصر':  (25.6872, 32.6396),
    'البحر الأحمر':    (26.9959, 33.8129), 'الوادى الجديد': (25.5189, 28.5094),
    'مطروح':           (31.3543, 27.2373), 'شمال سيناء':    (31.1283, 33.8000),
    'جنوب سيناء':      (29.3000, 34.1500),
}

# اسم المحافظة في Excel → pcode CAPMAS
GOV_PCODE_MAP = {
    'القاهرة': 'EG01',        'الاسكندرية': 'EG02',    'الإسكندرية': 'EG02',
    'بورسعيد': 'EG03',        'السويس': 'EG04',
    'دمياط': 'EG11',           'الدقهلية': 'EG12',
    'الشرقية': 'EG13',         'القليوبية': 'EG14',
    'كفر الشيخ': 'EG15',       'الغربية': 'EG16',
    'المنوفية': 'EG17',        'البحيرة': 'EG18',
    'الإسماعيلية': 'EG19',     'الجيزة': 'EG21',
    'بنى سويف': 'EG22',        'بني سويف': 'EG22',
    'الفيوم': 'EG23',           'المنيا': 'EG24',
    'أسيوط': 'EG25',            'اسيوط': 'EG25',
    'سوهاج': 'EG26',            'قنا': 'EG27',
    'أسوان': 'EG28',            'اسوان': 'EG28',
    'الأقصر': 'EG29',           'مدينة الأقصر': 'EG29',
    'البحر الأحمر': 'EG31',    'الوادى الجديد': 'EG32', 'الوادي الجديد': 'EG32',
    'مطروح': 'EG33',            'شمال سيناء': 'EG34',
    'جنوب سيناء': 'EG35',
}

# ── تنظيف النص ────────────────────────────────────────────────────────────
def clean(s):
    s = str(s).strip()
    return re.sub(r'[\u200b\u200c\u200d\ufeff]', '', s).strip()


# ── مطابقة اسم القرية مع قاموس الجيو ────────────────────────────────────
def match_village(name, geo_by_name, manual_map):
    cn = clean(name)
    if cn in geo_by_name:
        return geo_by_name[cn]
    mapped = manual_map.get(cn) or manual_map.get(name)
    if mapped and mapped in geo_by_name:
        return geo_by_name[mapped]
    seg = re.split(r'[+\-/،,]', cn)[0].strip()
    if seg and seg in geo_by_name:
        return geo_by_name[seg]
    for gname, gdata in geo_by_name.items():
        if len(cn) > 4 and (cn in gname or gname in cn):
            return gdata
    return None


# ── بناء قاموس تصحيح الأسماء لمحافظة ─────────────────────────────────────
def build_manual_map(gov_pcode):
    """
    يمكن توسيع هذا الجزء بملفات JSON خارجية لكل محافظة.
    مثال: data/name_corrections/EG12.json
    """
    COMMON = {
        # تصحيحات إملائية شائعة
        'ه': 'ة', 'ى': 'ي',
    }
    # تصحيحات خاصة بالدقهلية
    EG12 = {
        'البداله': 'البدالة', 'البداله+البرامون': 'البدالة',
        'الخياريه': 'الخيارية', 'الخياريه+ مدينة المنصورة': 'الخيارية',
        'الخياريه+البداله': 'الخيارية',
        'المعصره و كفورها': 'المعصرة وكفورها',
        'المندره': 'المندرة', 'المندره-طنامل الشرقى و عزبه الاتربه': 'المندرة',
        'اويش الحجر': 'أويش الحجر', 'اويش الحجر-كفر الشنهاب': 'أويش الحجر',
        'بداوى': 'بداوي', 'بدواى': 'بداوي', 'بدواي': 'بداوي',
        'منية بدواى': 'منية بداوي', 'منيه بدواى': 'منية بداوي',
        'كفر بدواى القديم': 'كفر بداوي القديم',
        'دنجواى': 'دنجواي', 'دنجواى / مدينة شربين': 'دنجواي',
        'سنيخت': 'سنبخت', 'مدينه سمنود+سنيخت': 'سنبخت',
        'مدينه سمنود': 'منية سمنود', 'منيه سمنود': 'منية سمنود',
        'صهرجت الكبرى وكفر جرجس يوسف': 'صهرجت الكبري وكفر جرجس يو',
        'طرانيس البحر+منية بدواى': 'طرانيس البحر',
        'طنامل الشرقى و عزبه الاتربه': 'طنامل الشرقي وعزبة الأترب',
        'طنامل الغربى': 'طنامل الغربي', 'طنامل الغربى-ميت دمسيس': 'طنامل الغربي',
        'كـفر العـــرب': 'كفر العرب',
        'كفر الترعة الجديد': 'كفر الترعة الجديدة',
        'كفر الترعه الجديد': 'كفر الترعة الجديدة',
        'كفر الترعه القديم': 'كفر الترعة القديم',
        'كفر الحطبه': 'كفر الحطبة',
        'كفر الدبوسى': 'كفر الدبوسي',
        'كفر الشنهاب-نوسا البحر': 'كفر الشنهاب',
        'كفر المندره': 'كفر المندرة', 'كفر المندره-المندره': 'كفر المندرة',
        'محلة انشاق': 'محلة أنشاق',
        'مدينة طلخا': 'مدينه طلخا',
        'مدينه المنصوره': 'قسم المنصورة',
        'ميت ابو الحارس': 'ميت أبو الحارس',
        'ميت اثنا': 'ميت أشنا', 'ميت اثينا': 'ميت أشنا', 'ميت اشنا': 'ميت أشنا',
        'ميت الكرما': 'ميت الكرماء', 'ميت الكرما / ميت نابت': 'ميت الكرماء',
        'ميت خميس': 'ميت خميس وكفر الموجي',
        'ميت دمسيس': 'ميت دمسيس وكفر أبو جرج',
        'ميت دمسيس+ميت اثينا': 'ميت دمسيس وكفر أبو جرج',
        'ميت عنتر / دار السـلام': 'ميت عنتر',
        'ميت عنتر / مدينة طلخا': 'ميت عنتر',
        'ميت نابت / كـفر العـــرب': 'ميت نابت',
        'ميت ناجى': 'ميت ناجي',
        'راس الخليج': 'رأس الخليج',
        'العوضيه': 'العوضية', 'السلاميه': 'السلامية',
        'الديرس وكفر لطيف': 'الدبوس وكفر لطيف',
        'الديرس وكفر لطيف-ميت ابو الحارس': 'الدبوس وكفر لطيف',
    }

    # يمكن تحميل تصحيحات إضافية من ملف JSON
    corrections_file = os.path.join(
        settings.BASE_DIR, 'data', 'name_corrections', f'{gov_pcode}.json'
    )
    extra = {}
    if os.path.exists(corrections_file):
        with open(corrections_file, 'r', encoding='utf-8') as f:
            extra = json.load(f)

    maps = {'EG12': EG12}
    result = maps.get(gov_pcode, {})
    result.update(extra)
    return result


class Command(BaseCommand):
    help = 'استيراد بيانات التعديات من Excel مع ربطها بالخرائط الجغرافية'

    def add_arguments(self, parser):
        parser.add_argument(
            'excel_files', nargs='+', type=str,
            help='مسار ملف Excel أو نمط glob (مثل: data/*.xlsx)'
        )
        parser.add_argument(
            '--geo-json', type=str,
            default=getattr(settings, 'GEO_JSON_PATH', ''),
            help='مسار ملف egypt_adm3_geo.json'
        )
        parser.add_argument(
            '--clear-gov', type=str, default='',
            help='مسح بيانات محافظة معينة قبل الاستيراد (مثال: EG12)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='تشغيل تجريبي بدون حفظ في قاعدة البيانات'
        )

    def handle(self, *args, **options):
        # ── تحميل الجيو جيسون ─────────────────────────────────────────────
        geo_json_path = options['geo_json']
        geo_all = []
        if geo_json_path and os.path.exists(geo_json_path):
            self.stdout.write(f'📂 تحميل الخرائط الجغرافية: {geo_json_path}')
            with open(geo_json_path, 'r', encoding='utf-8') as f:
                geo_all = json.load(f)
            self.stdout.write(self.style.SUCCESS(f'  ✓ {len(geo_all):,} مضلع جغرافي'))
        else:
            self.stdout.write(self.style.WARNING('⚠ لم يتم تحميل ملف الخرائط — سيتم استخدام إحداثيات تقديرية'))

        # ── مسح محافظة محددة ──────────────────────────────────────────────
        if options['clear_gov']:
            pcode = options['clear_gov']
            deleted, _ = Violation.objects.filter(governorate__pcode=pcode).delete()
            self.stdout.write(f'🗑  تم مسح {deleted:,} سجل من {pcode}')

        # ── توسيع glob ────────────────────────────────────────────────────
        files = []
        for pattern in options['excel_files']:
            expanded = glob.glob(pattern)
            files.extend(expanded if expanded else [pattern])

        total_imported = 0
        total_matched  = 0

        for excel_path in files:
            self.stdout.write(f'\n📊 معالجة: {excel_path}')
            try:
                result = self._import_file(
                    excel_path, geo_all,
                    dry_run=options['dry_run']
                )
                total_imported += result['imported']
                total_matched  += result['matched']
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ خطأ: {e}'))

        self.stdout.write('\n' + '═'*60)
        pct = round(total_matched / total_imported * 100) if total_imported else 0
        self.stdout.write(self.style.SUCCESS(
            f'✅ الإجمالي: {total_imported:,} سجل | '
            f'مرتبط جغرافياً: {total_matched:,} ({pct}%)'
        ))

    def _import_file(self, excel_path, geo_all, dry_run=False):
        df = pd.read_excel(excel_path)

        # ── تعرف على المحافظة من البيانات ─────────────────────────────────
        gov_name = str(df['اسم المحافظة'].dropna().iloc[0]).strip()
        gov_pcode = GOV_PCODE_MAP.get(gov_name)
        if not gov_pcode:
            self.stdout.write(self.style.WARNING(
                f'  ⚠ محافظة غير معروفة: "{gov_name}" — سيتم تخطيها'
            ))
            return {'imported': 0, 'matched': 0}

        self.stdout.write(f'  📍 المحافظة: {gov_name} ({gov_pcode})')

        # ── تحضير قاموس الجيو للمحافظة ───────────────────────────────────
        gov_geo = [v for v in geo_all if v['gov_pcode'] == gov_pcode]
        geo_by_name = {v['name_ar']: v for v in gov_geo}
        manual_map  = build_manual_map(gov_pcode)
        self.stdout.write(f'  🗺  مضلعات المحافظة: {len(gov_geo):,}')

        # ── تنظيف الأعمدة الرقمية ─────────────────────────────────────────
        num_cols = [
            'المسطح خارج الحياض م2',
            'مسطح التعدي علي المنفعة العامة م 2',
            'مسطح التعدي علي جسر نهر النيل م 2',
            'المسطح الاجمالي م2',
        ]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].replace('<Null>', None), errors='coerce'
                ).fillna(0)

        # ── إنشاء/تحديث سجل المحافظة ──────────────────────────────────────
        if not dry_run:
            gov_obj, _ = Governorate.objects.get_or_create(
                pcode=gov_pcode,
                defaults={'name_ar': gov_name, 'name_en': gov_pcode, 'has_data': True}
            )
            gov_obj.has_data = True
            gov_obj.name_ar  = gov_name
            gov_obj.save()

            # إنشاء المراكز الإدارية
            for district_name in df['اسم المركز'].dropna().unique():
                district_name = str(district_name).strip()
                District.objects.get_or_create(
                    pcode=f"{gov_pcode}_{district_name[:20]}",
                    defaults={
                        'governorate': gov_obj,
                        'name_ar': district_name,
                        'name_en': district_name,
                    }
                )

        # ── إحداثيات مركز المحافظة كاحتياطي ──────────────────────────────
        gov_center = GOV_CENTERS.get(gov_name, (26.8, 30.8))

        # مراكز الإدارية من الجيو
        district_centers = {}
        for v in gov_geo:
            dn = v['district_ar']
            if dn not in district_centers:
                district_centers[dn] = v['center']

        batch_name = os.path.basename(excel_path)
        imported = matched = 0
        violations_to_create = []

        for _, row in df.iterrows():
            district = clean(row['اسم المركز'])
            village  = clean(row['اسم القرية / المدينة'])

            # مطابقة جغرافية
            geo = match_village(village, geo_by_name, manual_map)

            if geo:
                lat, lon  = geo['center']
                pcode_val = geo['pcode']
                geo_exact = True
                matched  += 1
            else:
                # احتياطي: مركز المركز الإداري أو المحافظة
                base = district_centers.get(district, gov_center)
                random.seed(hash(str(row.get('الرمز *', row.name))))
                lat  = base[0] + random.uniform(-0.06, 0.06)
                lon  = base[1] + random.uniform(-0.06, 0.06)
                pcode_val = ''
                geo_exact = False

            v = Violation(
                governorate_id  = gov_obj.id if not dry_run else None,
                district_name   = district,
                village         = village,
                village_pcode   = pcode_val,
                code            = clean(row.get('الرمز *', '')),
                occupant        = clean(row.get('اسم المستغل في الطبيعة', '')),
                basin           = clean(row.get('اسم الحوض', '')),
                description     = clean(row.get('وصف الاستغلال', '')),
                area_outside    = float(row.get('المسطح خارج الحياض م2', 0) or 0),
                area_public     = float(row.get('مسطح التعدي علي المنفعة العامة م 2', 0) or 0),
                area_nile_bank  = float(row.get('مسطح التعدي علي جسر نهر النيل م 2', 0) or 0),
                area_total      = float(row.get('المسطح الاجمالي م2', 0) or 0),
                latitude        = round(lat, 6),
                longitude       = round(lon, 6),
                geo_exact       = geo_exact,
                import_batch    = batch_name,
            )
            violations_to_create.append(v)
            imported += 1

        if not dry_run:
            Violation.objects.bulk_create(violations_to_create, batch_size=500)

        pct = round(matched / imported * 100) if imported else 0
        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'  {prefix}✓ {imported:,} سجل | جيو: {matched:,} ({pct}%) | '
            f'تقديري: {imported - matched:,}'
        ))
        return {'imported': imported, 'matched': matched}
