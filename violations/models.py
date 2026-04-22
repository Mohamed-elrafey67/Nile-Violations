from django.db import models
from django.contrib.auth.models import User


class Governorate(models.Model):
    pcode    = models.CharField(max_length=10, unique=True, verbose_name='كود المحافظة')
    name_ar  = models.CharField(max_length=100, verbose_name='الاسم عربي')
    name_en  = models.CharField(max_length=100, verbose_name='الاسم إنجليزي')
    has_data = models.BooleanField(default=False, verbose_name='يوجد بيانات')

    class Meta:
        verbose_name        = 'محافظة'
        verbose_name_plural = 'المحافظات'
        ordering            = ['pcode']

    def __str__(self):
        return self.name_ar


class District(models.Model):
    governorate = models.ForeignKey(Governorate, on_delete=models.CASCADE,
                                    related_name='districts', verbose_name='المحافظة')
    pcode       = models.CharField(max_length=12, unique=True, verbose_name='كود المركز')
    name_ar     = models.CharField(max_length=100, verbose_name='الاسم عربي')
    name_en     = models.CharField(max_length=100, verbose_name='الاسم إنجليزي')

    class Meta:
        verbose_name        = 'مركز'
        verbose_name_plural = 'المراكز الإدارية'
        ordering            = ['governorate', 'name_ar']

    def __str__(self):
        return f"{self.name_ar} — {self.governorate.name_ar}"


class UserProfile(models.Model):
    ROLES = [
        ('viewer',    'مشاهد — عرض البيانات فقط'),
        ('data_entry','مدخل بيانات — إضافة وتعديل'),
        ('supervisor','مشرف — مراجعة وموافقة'),
        ('manager',   'مدير — صلاحيات كاملة'),
    ]
    user       = models.OneToOneField(User, on_delete=models.CASCADE,
                                      related_name='profile', verbose_name='المستخدم')
    role       = models.CharField(max_length=20, choices=ROLES,
                                  default='viewer', verbose_name='الدور')
    governorate = models.ForeignKey(Governorate, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    verbose_name='المحافظة المسؤول عنها')
    phone      = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    notes      = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'ملف مستخدم'
        verbose_name_plural = 'ملفات المستخدمين'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    def can_add(self):
        return self.role in ('data_entry', 'supervisor', 'manager')

    def can_approve(self):
        return self.role in ('supervisor', 'manager')

    def can_delete(self):
        return self.role == 'manager'


class Violation(models.Model):
    STATUS_CHOICES = [
        ('pending',  'في انتظار الموافقة'),
        ('approved', 'معتمد'),
        ('rejected', 'مرفوض'),
    ]

    # ── الموقع الإداري ──────────────────────────────────────────
    governorate   = models.ForeignKey(Governorate, on_delete=models.SET_NULL,
                                      null=True, blank=True,
                                      related_name='violations', verbose_name='المحافظة')
    district_name = models.CharField(max_length=100, verbose_name='اسم المركز')
    village       = models.CharField(max_length=200, verbose_name='القرية / المدينة')
    village_pcode = models.CharField(max_length=15, blank=True, default='',
                                     verbose_name='كود القرية', db_index=True)

    # ── بيانات السجل ─────────────────────────────────────────────
    code        = models.CharField(max_length=20, verbose_name='الرمز', db_index=True)
    occupant    = models.CharField(max_length=200, verbose_name='اسم المستغل')
    basin       = models.CharField(max_length=300, verbose_name='اسم الحوض')
    description = models.CharField(max_length=500, verbose_name='وصف الاستغلال', db_index=True)

    # ── المساحات ─────────────────────────────────────────────────
    area_outside   = models.FloatField(default=0, verbose_name='المسطح خارج الحياض م²')
    area_public    = models.FloatField(default=0, verbose_name='تعدي على المنفعة العامة م²')
    area_nile_bank = models.FloatField(default=0, verbose_name='تعدي على جسر نهر النيل م²')
    area_total     = models.FloatField(default=0, verbose_name='المسطح الإجمالي م²', db_index=True)

    # ── الإحداثيات ───────────────────────────────────────────────
    latitude  = models.FloatField(verbose_name='خط العرض')
    longitude = models.FloatField(verbose_name='خط الطول')
    geo_exact = models.BooleanField(default=False, verbose_name='إحداثيات دقيقة')

    # ── الحالة والموافقة ─────────────────────────────────────────
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                    default='approved', verbose_name='الحالة', db_index=True)
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name='submitted_violations',
                                     verbose_name='أُدخل بواسطة')
    reviewed_by  = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name='reviewed_violations',
                                     verbose_name='راجعه')
    review_notes = models.TextField(blank=True, verbose_name='ملاحظات المراجعة')
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإدخال')
    reviewed_at  = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ المراجعة')

    # ── الصور والملاحظات ─────────────────────────────────────────
    field_notes  = models.TextField(blank=True, verbose_name='ملاحظات ميدانية')
    import_batch = models.CharField(max_length=100, blank=True, default='',
                                    verbose_name='دفعة الاستيراد')

    class Meta:
        verbose_name        = 'تعدٍّ'
        verbose_name_plural = 'التعديات على نهر النيل'
        ordering            = ['-submitted_at']
        indexes = [
            models.Index(fields=['governorate', 'district_name']),
            models.Index(fields=['status']),
            models.Index(fields=['village_pcode']),
        ]

    def __str__(self):
        gov = self.governorate.name_ar if self.governorate else '—'
        return f"{self.code} | {self.village} ({self.district_name} – {gov})"


class ViolationImage(models.Model):
    violation   = models.ForeignKey(Violation, on_delete=models.CASCADE,
                                    related_name='images', verbose_name='التعدي')
    image       = models.ImageField(upload_to='violations/%Y/%m/', verbose_name='الصورة')
    caption     = models.CharField(max_length=200, blank=True, verbose_name='وصف الصورة')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    null=True, verbose_name='رُفعت بواسطة')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'صورة'
        verbose_name_plural = 'صور التعديات'

    def __str__(self):
        return f"صورة {self.violation.code}"


class ViolationNote(models.Model):
    violation  = models.ForeignKey(Violation, on_delete=models.CASCADE,
                                   related_name='notes', verbose_name='التعدي')
    user       = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, verbose_name='المستخدم')
    text       = models.TextField(verbose_name='نص الملاحظة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'ملاحظة'
        verbose_name_plural = 'الملاحظات'
        ordering            = ['-created_at']

    def __str__(self):
        return f"ملاحظة على {self.violation.code}"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('login',    'تسجيل دخول'),
        ('logout',   'تسجيل خروج'),
        ('add',      'إضافة سجل'),
        ('edit',     'تعديل سجل'),
        ('approve',  'موافقة على سجل'),
        ('reject',   'رفض سجل'),
        ('delete',   'حذف سجل'),
        ('export',   'تصدير تقرير'),
        ('import',   'استيراد بيانات'),
        ('login_fail', 'محاولة دخول فاشلة'),
    ]

    user       = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, blank=True, verbose_name='المستخدم')
    action     = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='الحدث')
    target     = models.CharField(max_length=200, blank=True, verbose_name='الهدف')
    details    = models.TextField(blank=True, verbose_name='التفاصيل')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='عنوان IP')
    timestamp  = models.DateTimeField(auto_now_add=True, verbose_name='التوقيت', db_index=True)

    class Meta:
        verbose_name        = 'سجل نشاط'
        verbose_name_plural = 'سجل الأنشطة'
        ordering            = ['-timestamp']

    def __str__(self):
        user = self.user.username if self.user else 'غير معروف'
        return f"{self.get_action_display()} — {user} — {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
