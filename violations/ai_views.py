"""
AI Views — violations/ai_views.py
واجهات Django للذكاء الاصطناعي
"""
import json
import base64
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .views import get_role
from . import ai_service


def _check_ollama(request):
    """تحقق من توفر Ollama وأعد خطأ إذا لم يكن متاحاً."""
    ok, models = ai_service.check_ollama()
    if not ok:
        return JsonResponse({
            'error': 'Ollama غير مشغّل',
            'detail': 'شغّل Ollama أولاً: ollama serve',
            'install': 'https://ollama.com/download',
        }, status=503)
    return None


# ══════════════════════════════════════════════════════════════════
# ١. المساعد الذكي
# ══════════════════════════════════════════════════════════════════

@login_required(login_url='login')
def ai_chat(request):
    """المساعد الذكي — يجيب على أسئلة البيانات بالعربية."""
    err = _check_ollama(request)
    if err: return err

    try:
        data    = json.loads(request.body)
        question = data.get('question', '').strip()
        history  = data.get('history', [])
    except Exception:
        return JsonResponse({'error': 'بيانات غير صالحة'}, status=400)

    if not question:
        return JsonResponse({'error': 'السؤال فارغ'}, status=400)

    answer = ai_service.smart_assistant(question, history)
    return JsonResponse({'answer': answer, 'question': question})


# ══════════════════════════════════════════════════════════════════
# ٢. كشف التكرار
# ══════════════════════════════════════════════════════════════════

@login_required(login_url='login')
def ai_detect_duplicates(request, pk):
    """كشف السجلات المشابهة لسجل معين."""
    err = _check_ollama(request)
    # Allow fallback to simple check even without Ollama
    threshold = float(request.GET.get('threshold', 0.85))
    duplicates = ai_service.detect_duplicates(pk, threshold)
    return JsonResponse({
        'duplicates': duplicates,
        'count': len(duplicates),
        'ai_used': err is None,
    })


# ══════════════════════════════════════════════════════════════════
# ٣. تصنيف وصف الاستغلال
# ══════════════════════════════════════════════════════════════════

@login_required(login_url='login')
def ai_classify(request):
    """تصنيف وصف الاستغلال تلقائياً."""
    try:
        data = json.loads(request.body)
        text = data.get('description', '').strip()
    except Exception:
        return JsonResponse({'error': 'بيانات غير صالحة'}, status=400)

    if not text:
        return JsonResponse({'error': 'النص فارغ'}, status=400)

    result = ai_service.classify_description(text)
    return JsonResponse(result)


# ══════════════════════════════════════════════════════════════════
# ٤. تحليل الصور
# ══════════════════════════════════════════════════════════════════

@login_required(login_url='login')
@require_POST
def ai_analyze_image(request):
    """تحليل صورة التعدي باستخدام الذكاء الاصطناعي."""
    err = _check_ollama(request)
    if err: return err

    # صورة مرفوعة أو base64
    if 'image' in request.FILES:
        img_file = request.FILES['image']
        img_b64  = base64.b64encode(img_file.read()).decode('utf-8')
    else:
        try:
            data    = json.loads(request.body)
            img_b64 = data.get('image_base64', '')
        except Exception:
            return JsonResponse({'error': 'لم يتم إرسال صورة'}, status=400)

    if not img_b64:
        return JsonResponse({'error': 'الصورة فارغة'}, status=400)

    result = ai_service.analyze_image(img_b64, is_base64=True)
    return JsonResponse(result)


# ══════════════════════════════════════════════════════════════════
# ٥. توليد التقارير
# ══════════════════════════════════════════════════════════════════

@login_required(login_url='login')
def ai_generate_report(request):
    """توليد تقرير نصي احترافي بالعربية."""
    err = _check_ollama(request)
    if err: return err

    filters = {
        'gov':      request.GET.get('gov', ''),
        'district': request.GET.get('district', ''),
        'min_area': request.GET.get('min_area', ''),
    }
    result = ai_service.generate_report(filters)
    return JsonResponse(result)


# ══════════════════════════════════════════════════════════════════
# حالة الذكاء الاصطناعي
# ══════════════════════════════════════════════════════════════════

@login_required(login_url='login')
def ai_status(request):
    """حالة نماذج الذكاء الاصطناعي."""
    ok, models = ai_service.check_ollama()
    required = ['llama3.2', 'nomic-embed-text', 'llava']
    return JsonResponse({
        'ollama_running': ok,
        'models':  models,
        'ready': {
            m: any(m in installed for installed in models)
            for m in required
        },
        'install_cmd': 'ollama pull llama3.2 && ollama pull nomic-embed-text && ollama pull llava',
    })
