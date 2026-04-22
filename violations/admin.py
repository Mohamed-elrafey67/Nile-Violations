from django.contrib import admin
from django.db.models import Count, Sum
from .models import Violation, Governorate, District, UserProfile, ViolationImage, ViolationNote


@admin.register(Governorate)
class GovernorateAdmin(admin.ModelAdmin):
    list_display  = ['pcode', 'name_ar', 'name_en', 'has_data']
    search_fields = ['name_ar', 'pcode']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'role', 'governorate', 'phone']
    list_filter   = ['role', 'governorate']
    search_fields = ['user__username', 'user__first_name']

    def get_role_display(self, obj):
        return obj.get_role_display()


@admin.register(Violation)
class ViolationAdmin(admin.ModelAdmin):
    list_display  = ['code', 'governorate', 'district_name', 'village',
                     'description', 'area_total', 'status', 'submitted_by', 'submitted_at']
    list_filter   = ['status', 'governorate', 'geo_exact']
    search_fields = ['code', 'occupant', 'village', 'basin']
    ordering      = ['-submitted_at']
    readonly_fields = ['submitted_at', 'reviewed_at', 'import_batch']
    actions       = ['approve_selected', 'reject_selected']

    def approve_selected(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='approved', reviewed_by=request.user)
        self.message_user(request, f'تم اعتماد {updated} سجل')
    approve_selected.short_description = 'اعتماد السجلات المختارة'

    def reject_selected(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='rejected', reviewed_by=request.user)
        self.message_user(request, f'تم رفض {updated} سجل')
    reject_selected.short_description = 'رفض السجلات المختارة'


@admin.register(ViolationImage)
class ViolationImageAdmin(admin.ModelAdmin):
    list_display = ['violation', 'caption', 'uploaded_by', 'uploaded_at']


@admin.register(ViolationNote)
class ViolationNoteAdmin(admin.ModelAdmin):
    list_display = ['violation', 'user', 'created_at']
