"""
تحميل مكتبات JavaScript/CSS المطلوبة للخريطة وحفظها محلياً.

الاستخدام:
    python manage.py download_libs
"""

import os
import urllib.request
import urllib.error
from django.core.management.base import BaseCommand
from django.conf import settings


LIBS = {
    # Leaflet
    'violations/libs/leaflet/leaflet.js':
        'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
    'violations/libs/leaflet/leaflet.css':
        'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
    'violations/libs/leaflet/images/marker-icon.png':
        'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    'violations/libs/leaflet/images/marker-icon-2x.png':
        'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    'violations/libs/leaflet/images/marker-shadow.png':
        'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    'violations/libs/leaflet/images/layers.png':
        'https://unpkg.com/leaflet@1.9.4/dist/images/layers.png',
    'violations/libs/leaflet/images/layers-2x.png':
        'https://unpkg.com/leaflet@1.9.4/dist/images/layers-2x.png',

    # MarkerCluster
    'violations/libs/markercluster/leaflet.markercluster.js':
        'https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js',
    'violations/libs/markercluster/MarkerCluster.css':
        'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css',
    'violations/libs/markercluster/MarkerCluster.Default.css':
        'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css',

    # Font Awesome
    'violations/libs/fontawesome/css/all.min.css':
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css',
    'violations/libs/fontawesome/webfonts/fa-solid-900.woff2':
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/webfonts/fa-solid-900.woff2',
    'violations/libs/fontawesome/webfonts/fa-solid-900.ttf':
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/webfonts/fa-solid-900.ttf',
    'violations/libs/fontawesome/webfonts/fa-regular-400.woff2':
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/webfonts/fa-regular-400.woff2',
    'violations/libs/fontawesome/webfonts/fa-brands-400.woff2':
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/webfonts/fa-brands-400.woff2',
}

# الملفات الضرورية فقط (بدونها الخريطة لا تعمل)
ESSENTIAL = {
    'violations/libs/leaflet/leaflet.js',
    'violations/libs/leaflet/leaflet.css',
    'violations/libs/markercluster/leaflet.markercluster.js',
    'violations/libs/markercluster/MarkerCluster.css',
    'violations/libs/markercluster/MarkerCluster.Default.css',
}


class Command(BaseCommand):
    help = 'تحميل مكتبات الخريطة (Leaflet + MarkerCluster + FontAwesome) محلياً'

    def add_arguments(self, parser):
        parser.add_argument(
            '--essential-only',
            action='store_true',
            help='تحميل الملفات الضرورية فقط (أسرع)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='إعادة التحميل حتى لو الملف موجود'
        )

    def handle(self, *args, **options):
        static_dir  = os.path.join(settings.BASE_DIR, 'violations', 'static')
        essential   = options['essential_only']
        force       = options['force']

        libs = {k: v for k, v in LIBS.items()
                if not essential or k in ESSENTIAL}

        self.stdout.write(f'📦 تحميل {len(libs)} ملف...\n')

        ok = skipped = failed = 0

        for rel_path, url in libs.items():
            dest = os.path.join(static_dir, rel_path.replace('/', os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)

            if os.path.exists(dest) and not force:
                self.stdout.write(f'  ⏭  موجود مسبقاً: {rel_path}')
                skipped += 1
                continue

            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    content = resp.read()
                with open(dest, 'wb') as f:
                    f.write(content)
                size = len(content) // 1024
                self.stdout.write(f'  ✅ {rel_path} ({size} KB)')
                ok += 1

            except urllib.error.URLError as e:
                self.stdout.write(self.style.ERROR(f'  ✗ فشل: {rel_path} — {e}'))
                failed += 1

        # ── تصحيح مسار الصور في leaflet.css ───────────────────────────────
        css_path = os.path.join(static_dir,
                                'violations', 'libs', 'leaflet', 'leaflet.css')
        if os.path.exists(css_path):
            with open(css_path, 'r', encoding='utf-8') as f:
                css = f.read()
            css = css.replace(
                'url(images/',
                'url(../leaflet/images/'
            )
            with open(css_path, 'w', encoding='utf-8') as f:
                f.write(css)

        # ── تصحيح مسار الخطوط في fontawesome ──────────────────────────────
        fa_css = os.path.join(static_dir,
                              'violations', 'libs', 'fontawesome', 'css', 'all.min.css')
        if os.path.exists(fa_css):
            with open(fa_css, 'r', encoding='utf-8') as f:
                css = f.read()
            css = css.replace('../webfonts/', '../webfonts/')
            with open(fa_css, 'w', encoding='utf-8') as f:
                f.write(css)

        self.stdout.write('\n' + '═' * 50)
        if failed == 0:
            self.stdout.write(self.style.SUCCESS(
                f'✅ تم: {ok} ملف | مُتخطَّى: {skipped} | فشل: {failed}\n'
                f'\nالخطوة التالية:\n'
                f'  python manage.py runserver'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'⚠ تم: {ok} | مُتخطَّى: {skipped} | فشل: {failed}\n'
                f'تحقق من اتصال الإنترنت وأعد المحاولة.'
            ))
            if failed > 0 and ok > 0:
                self.stdout.write(
                    '\nيمكن تشغيل التطبيق لكن بعض الأيقونات قد لا تظهر.\n'
                    'الخريطة ستعمل إذا نجح تحميل Leaflet.'
                )
