"""
خدمة الذكاء الاصطناعي — violations/ai_service.py
تشمل: المساعد الذكي، كشف التكرار، تصنيف الاستغلال، تحليل الصور، التقارير
"""
import json
import base64
import urllib.request
import urllib.error
from django.db.models import Count, Sum, Avg, Q

OLLAMA_URL   = 'http://localhost:11434/api'
CHAT_MODEL   = 'llama3.2'
EMBED_MODEL  = 'nomic-embed-text'
VISION_MODEL = 'llava'


# ══════════════════════════════════════════════════════════════════
# CORE — اتصال بـ Ollama
# ══════════════════════════════════════════════════════════════════

def _ollama_request(endpoint, payload, timeout=60):
    """إرسال طلب لـ Ollama API."""
    data = json.dumps(payload).encode('utf-8')
    req  = urllib.request.Request(
        f'{OLLAMA_URL}/{endpoint}',
        data=data,
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError:
        return None
    except Exception:
        return None


def check_ollama():
    """التحقق من تشغيل Ollama."""
    try:
        req  = urllib.request.Request(f'{OLLAMA_URL.replace("/api","")}/api/tags')
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            models = [m['name'] for m in data.get('models', [])]
            return True, models
    except Exception:
        return False, []


def _chat(messages, model=CHAT_MODEL, temperature=0.3):
    """محادثة مع النموذج."""
    result = _ollama_request('chat', {
        'model':    model,
        'messages': messages,
        'stream':   False,
        'options':  {'temperature': temperature, 'num_predict': 1024},
    }, timeout=120)
    if result:
        return result.get('message', {}).get('content', '')
    return None


def _embed(text, model=EMBED_MODEL):
    """توليد embedding لنص."""
    result = _ollama_request('embeddings', {
        'model':  model,
        'prompt': text,
    }, timeout=30)
    if result:
        return result.get('embedding', [])
    return []


def _cosine_similarity(a, b):
    """حساب التشابه بين متجهين."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0


# ══════════════════════════════════════════════════════════════════
# ١. المساعد الذكي — Smart Assistant
# ══════════════════════════════════════════════════════════════════

def build_data_context():
    """بناء سياق البيانات للمساعد."""
    from .models import Violation, Governorate

    stats = Violation.objects.filter(status='approved').aggregate(
        total=Count('id'), area=Sum('area_total'),
        avg_area=Avg('area_total'),
    )
    by_gov = list(
        Violation.objects.filter(status='approved')
        .values('governorate__name_ar')
        .annotate(count=Count('id'), area=Sum('area_total'))
        .order_by('-count')[:10]
    )
    by_desc = list(
        Violation.objects.filter(status='approved')
        .values('description')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    by_district = list(
        Violation.objects.filter(status='approved')
        .values('district_name', 'governorate__name_ar')
        .annotate(count=Count('id'), area=Sum('area_total'))
        .order_by('-count')[:10]
    )

    ctx = f"""
أنت مساعد ذكي متخصص في منظومة توثيق أراضي طرح النهر — وزارة الموارد المائية والري.
أجب دائماً بالعربية بشكل مختصر ومهني.

إحصائيات المنظومة الحالية:
- إجمالي التعديات المعتمدة: {stats['total']:,}
- إجمالي المساحة: {round(stats['area'] or 0):,} م²
- متوسط مساحة التعدي: {round(stats['avg_area'] or 0):,} م²

أعلى المحافظات تعدياً:
{chr(10).join(f"  - {g['governorate__name_ar']}: {g['count']} تعدٍّ | {round(g['area'] or 0):,} م²" for g in by_gov)}

أكثر أنواع الاستغلال:
{chr(10).join(f"  - {d['description']}: {d['count']}" for d in by_desc[:5])}

أعلى المراكز تعدياً:
{chr(10).join(f"  - {d['district_name']} ({d['governorate__name_ar']}): {d['count']} تعدٍّ" for d in by_district)}
"""
    return ctx


def smart_assistant(question, conversation_history=None):
    """
    المساعد الذكي — يجيب على أسئلة البيانات بالعربية.
    conversation_history: قائمة [{role, content}] للمحادثة السابقة
    """
    system_ctx = build_data_context()
    messages   = [{'role': 'system', 'content': system_ctx}]

    if conversation_history:
        messages.extend(conversation_history[-6:])  # آخر 3 رسائل

    messages.append({'role': 'user', 'content': question})

    answer = _chat(messages, temperature=0.4)
    return answer or 'عذراً، تعذّر الاتصال بنموذج الذكاء الاصطناعي. تأكد من تشغيل Ollama.'


# ══════════════════════════════════════════════════════════════════
# ٢. كشف التكرار والتلاعب
# ══════════════════════════════════════════════════════════════════

def detect_duplicates(violation_id, threshold=0.85):
    """
    كشف السجلات المشابهة لسجل معين.
    threshold: نسبة التشابه (0-1)، كلما ارتفعت كلما كان التشابه أقوى
    """
    from .models import Violation

    try:
        v = Violation.objects.get(pk=violation_id)
    except Violation.DoesNotExist:
        return []

    # بناء نص وصفي للسجل
    target_text = f"{v.occupant} {v.village} {v.district_name} {v.description} {v.basin}"
    target_emb  = _embed(target_text)

    if not target_emb:
        # fallback: مطابقة نصية بسيطة إذا لم يعمل الـ embedding
        return _simple_duplicate_check(v)

    # فحص السجلات المشابهة في نفس المحافظة
    candidates = Violation.objects.filter(
        governorate=v.governorate
    ).exclude(pk=violation_id).exclude(status='rejected')[:500]

    duplicates = []
    for cand in candidates:
        cand_text = f"{cand.occupant} {cand.village} {cand.district_name} {cand.description} {cand.basin}"
        cand_emb  = _embed(cand_text)
        similarity = _cosine_similarity(target_emb, cand_emb)

        if similarity >= threshold:
            # فحص قرب الإحداثيات
            lat_diff = abs(v.latitude  - cand.latitude)
            lon_diff = abs(v.longitude - cand.longitude)
            geo_near = lat_diff < 0.01 and lon_diff < 0.01  # ~1km

            duplicates.append({
                'id':         cand.id,
                'code':       cand.code,
                'village':    cand.village,
                'occupant':   cand.occupant,
                'area_total': cand.area_total,
                'similarity': round(similarity * 100, 1),
                'geo_near':   geo_near,
                'risk':       'عالي' if similarity > 0.92 and geo_near else
                              'متوسط' if similarity > 0.87 else 'منخفض',
            })

    duplicates.sort(key=lambda x: x['similarity'], reverse=True)
    return duplicates[:10]


def _simple_duplicate_check(v):
    """كشف تكرار بسيط بدون embedding."""
    from .models import Violation
    import re

    def normalize(s):
        return re.sub(r'\s+', '', str(s or '').strip())

    candidates = Violation.objects.filter(
        governorate=v.governorate,
        village=v.village,
    ).exclude(pk=v.id).exclude(status='rejected')

    results = []
    for c in candidates:
        same_occupant = normalize(v.occupant) == normalize(c.occupant)
        area_diff = abs(v.area_total - c.area_total) / max(v.area_total, 1)
        if same_occupant or area_diff < 0.05:
            results.append({
                'id': c.id, 'code': c.code,
                'village': c.village, 'occupant': c.occupant,
                'area_total': c.area_total,
                'similarity': 95 if same_occupant else 80,
                'geo_near': True,
                'risk': 'عالي' if same_occupant else 'متوسط',
            })
    return results


# ══════════════════════════════════════════════════════════════════
# ٣. تصنيف وصف الاستغلال تلقائياً
# ══════════════════════════════════════════════════════════════════

# فئات الاستغلال المعتمدة
USAGE_CATEGORIES = {
    'مبنى سكني':   ['مبني', 'منزل', 'عمارة', 'شقة', 'دور'],
    'زراعي':       ['مزروعة', 'زراعة', 'بستان', 'مزرعة', 'محصول', 'معروش'],
    'فضاء':        ['فضاء', 'أرض فضاء', 'خالية', 'فراغ'],
    'تجاري':       ['محل', 'مخزن', 'مخبز', 'ورشة', 'مصنع', 'سوق'],
    'مياه':        ['بركة', 'مياه', 'حوض', 'نهر'],
    'بنية تحتية':  ['محول', 'كهرباء', 'طلمبات', 'مشاية', 'طريق'],
    'ردم':         ['ردم', 'ردم نيل', 'ردم نهر'],
}


def classify_description(description_text):
    """
    تصنيف وصف الاستغلال باستخدام الذكاء الاصطناعي.
    يُعيد: الفئة المقترحة + درجة الثقة + تفسير
    """
    # محاولة التصنيف القاعدي أولاً (سريع)
    text_lower = description_text.strip().lower()
    for category, keywords in USAGE_CATEGORIES.items():
        if any(kw in text_lower for kw in keywords):
            return {
                'category':    category,
                'confidence':  'عالية',
                'method':      'قاعدة نصية',
                'explanation': f'الكلمة المطابقة: "{next(kw for kw in keywords if kw in text_lower)}"',
            }

    # إذا لم تُطابق — استخدم النموذج
    prompt = f"""صنّف وصف الاستغلال التالي في إحدى هذه الفئات فقط:
{', '.join(USAGE_CATEGORIES.keys())}

الوصف: "{description_text}"

أجب بصيغة JSON فقط:
{{"category": "اسم الفئة", "confidence": "عالية/متوسطة/منخفضة", "explanation": "سبب قصير"}}"""

    result = _chat([{'role': 'user', 'content': prompt}], temperature=0.1)
    if result:
        try:
            import re
            match = re.search(r'\{.*?\}', result, re.DOTALL)
            if match:
                data = json.loads(match.group())
                data['method'] = 'نموذج AI'
                return data
        except Exception:
            pass

    return {
        'category':    'غير محدد',
        'confidence':  'منخفضة',
        'method':      'غير متاح',
        'explanation': 'تعذّر التصنيف',
    }


# ══════════════════════════════════════════════════════════════════
# ٤. تحليل الصور
# ══════════════════════════════════════════════════════════════════

def analyze_image(image_path_or_base64, is_base64=False):
    """
    تحليل صورة التعدي باستخدام نموذج LLaVA.
    يُعيد: وصف الاستغلال + تقدير نوعه + ملاحظات
    """
    if not is_base64:
        try:
            with open(image_path_or_base64, 'rb') as f:
                img_data = base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            return {'error': f'تعذّر قراءة الصورة: {e}'}
    else:
        img_data = image_path_or_base64

    prompt = """حلل هذه الصورة لتعدٍّ على أراضي طرح النهر وأجب بالعربية:
1. ما نوع الاستخدام الموجود؟ (مبنى، زراعة، فضاء، ردم، إلخ)
2. ما الحالة العامة للتعدي؟
3. هل يوجد مبانٍ أو إنشاءات؟
4. ما تقديرك للمساحة المرئية؟
5. أي ملاحظات مهمة أخرى؟"""

    result = _ollama_request('generate', {
        'model':   VISION_MODEL,
        'prompt':  prompt,
        'images':  [img_data],
        'stream':  False,
        'options': {'temperature': 0.2},
    }, timeout=120)

    if result:
        analysis = result.get('response', '')
        # استخراج التصنيف المقترح
        suggested = classify_description(analysis)
        return {
            'analysis':          analysis,
            'suggested_category': suggested.get('category', 'غير محدد'),
            'confidence':        suggested.get('confidence', '—'),
        }

    return {
        'analysis':          'تعذّر تحليل الصورة. تأكد من تثبيت نموذج llava.',
        'suggested_category': 'غير محدد',
        'confidence':        'منخفضة',
    }


# ══════════════════════════════════════════════════════════════════
# ٥. توليد التقارير النصية
# ══════════════════════════════════════════════════════════════════

def generate_report(filters=None):
    """
    توليد تقرير نصي احترافي بالعربية بناءً على الفلاتر الحالية.
    filters: dict مثل {'gov': 'EG12', 'district': 'أجا'}
    """
    from .models import Violation

    qs = Violation.objects.filter(status='approved')
    filter_desc = 'جميع المحافظات'

    if filters:
        if filters.get('gov'):
            qs = qs.filter(governorate__pcode=filters['gov'])
            try:
                from .models import Governorate
                gov = Governorate.objects.get(pcode=filters['gov'])
                filter_desc = f'محافظة {gov.name_ar}'
            except Exception:
                pass
        if filters.get('district'):
            qs = qs.filter(district_name=filters['district'])
            filter_desc += f' — مركز {filters["district"]}'
        if filters.get('min_area'):
            qs = qs.filter(area_total__gte=float(filters['min_area']))

    # جمع الإحصائيات
    stats = qs.aggregate(
        total=Count('id'), area=Sum('area_total'), avg=Avg('area_total'),
        nile=Sum('area_nile_bank'), public=Sum('area_public'),
    )
    top_villages = list(
        qs.values('village', 'district_name')
        .annotate(count=Count('id'), area=Sum('area_total'))
        .order_by('-count')[:5]
    )
    top_desc = list(
        qs.values('description')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    from django.utils import timezone
    today = timezone.now().strftime('%Y/%m/%d')

    data_summary = f"""
بيانات التقرير ({filter_desc}) — بتاريخ {today}:
- عدد التعديات: {stats['total'] or 0:,}
- المساحة الإجمالية: {round(stats['area'] or 0):,} م²
- متوسط مساحة التعدي: {round(stats['avg'] or 0):,} م²
- تعدي على جسور النيل: {round(stats['nile'] or 0):,} م²
- تعدي على المنفعة العامة: {round(stats['public'] or 0):,} م²

أعلى القرى تعدياً:
{chr(10).join(f"  {i+1}. {v['village']} ({v['district_name']}): {v['count']} تعدٍّ | {round(v['area'] or 0):,} م²" for i, v in enumerate(top_villages))}

أكثر أنواع الاستغلال:
{chr(10).join(f"  - {d['description']}: {d['count']} تعدٍّ" for d in top_desc)}
"""

    prompt = f"""أنت خبير في شؤون الموارد المائية والأراضي في مصر.
اكتب تقريراً رسمياً مهنياً باللغة العربية الفصحى بناءً على البيانات التالية.
التقرير يجب أن يتضمن: المقدمة، أبرز النتائج، التوصيات.
اجعله رسمياً ومناسباً للرفع لوزارة الموارد المائية والري.

{data_summary}"""

    report = _chat([{'role': 'user', 'content': prompt}], temperature=0.5)

    return {
        'report':       report or 'تعذّر توليد التقرير. تأكد من تشغيل Ollama.',
        'stats':        stats,
        'filter_desc':  filter_desc,
        'date':         today,
    }
