"""
إعداد الذكاء الاصطناعي — تشغيل هذا الملف مرة واحدة لتحميل النماذج
"""
import subprocess, sys, os

MODELS = [
    ('llama3.2',          'المساعد الذكي والتقارير (2GB)'),
    ('nomic-embed-text',  'كشف التكرار والتشابه (274MB)'),
    ('llava',             'تحليل الصور (4.7GB)'),
]

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr

def check_ollama():
    ok, out, _ = run('ollama --version')
    if ok:
        print(f'✅ Ollama مثبت: {out.strip()}')
        return True
    print('❌ Ollama غير مثبت')
    print('   حمّله من: https://ollama.com/download')
    return False

def pull_models():
    for model, desc in MODELS:
        print(f'\n⏳ تحميل {model} — {desc}')
        ok, _, err = run(f'ollama pull {model}')
        if ok:
            print(f'   ✅ تم تحميل {model}')
        else:
            print(f'   ❌ فشل: {err[:100]}')

if __name__ == '__main__':
    print('=' * 55)
    print('  إعداد الذكاء الاصطناعي — منظومة توثيق أراضي طرح النهر')
    print('=' * 55)
    if check_ollama():
        pull_models()
        print('\n✅ جاهز! شغّل: python manage.py runserver')
    else:
        print('\nبعد تثبيت Ollama شغّل هذا الملف مرة أخرى')
