"""
سكريبت لإنشاء مستخدمين تجريبيين بالأدوار الأربعة.
شغّله مرة واحدة: python setup_users.py
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nile_violations.settings')
django.setup()

from django.contrib.auth.models import User
from violations.models import UserProfile, Governorate

USERS = [
    {'username':'manager',    'password':'Manager@123',   'first_name':'مدير النظام',      'role':'manager'},
    {'username':'supervisor', 'password':'Supervisor@123','first_name':'المشرف العام',      'role':'supervisor'},
    {'username':'data_entry', 'password':'DataEntry@123', 'first_name':'مدخل البيانات',    'role':'data_entry'},
    {'username':'viewer',     'password':'Viewer@123',    'first_name':'مستخدم مشاهد',     'role':'viewer'},
]

for u in USERS:
    user, created = User.objects.get_or_create(username=u['username'])
    user.set_password(u['password'])
    user.first_name = u['first_name']
    user.save()
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = u['role']
    profile.save()
    status = 'تم إنشاؤه' if created else 'تم تحديثه'
    print(f"  {'✓'} {u['first_name']} ({u['username']}) — {status}")

print("\nبيانات تسجيل الدخول:")
print("─"*45)
for u in USERS:
    print(f"  {u['first_name']:<20} | {u['username']:<12} | {u['password']}")
