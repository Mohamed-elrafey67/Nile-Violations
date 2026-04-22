from django.urls import path
from django.shortcuts import render
from . import views
from . import ai_views


def map_test(request):
    return render(request, 'violations/map_test.html')


urlpatterns = [
    # Pages
    path('',          views.map_view,        name='map'),
    path('login/',    views.login_view,       name='login'),
    path('logout/',   views.logout_view,      name='logout'),
    path('test/',     map_test,               name='map_test'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # Map APIs
    path('api/violations/',               views.violations_api,        name='violations_api'),
    path('api/violations/add/',           views.add_violation_api,     name='add_violation'),
    path('api/violations/pending/',       views.pending_api,           name='pending_violations'),
    path('api/violations/<int:pk>/',      views.violation_detail_api,  name='violation_detail'),
    path('api/violations/<int:pk>/edit/', views.edit_violation_api,    name='edit_violation'),
    path('api/violations/<int:pk>/approve/', views.approve_violation_api, name='approve_violation'),
    path('api/violations/<int:pk>/notes/', views.notes_api,            name='violation_notes'),
    path('api/violations/<int:pk>/images/', views.upload_image_api,    name='upload_image'),
    path('api/geo/<str:gov_pcode>/',      views.geo_gov_api,           name='geo_gov_api'),
    path('api/filter-options/',           views.filter_options_api,    name='filter_options_api'),
    path('api/govs-summary/',             views.govs_summary_api,      name='govs_summary_api'),
    path('api/violations/rejected/',      views.rejected_api,          name='rejected_violations'),
    path('api/violations/<int:pk>/restore/', views.restore_violation_api, name='restore_violation'),

    # Export
    path('api/export/excel/', views.export_excel_view, name='export_excel'),
    path('api/export/pdf/',   views.export_pdf_view,   name='export_pdf'),

    # Admin Dashboard APIs
    path('admin-dashboard/api/stats/',          views.admin_stats_api,      name='admin_stats'),
    path('admin-dashboard/api/users/',          views.admin_users_api,      name='admin_users'),
    path('admin-dashboard/api/users/<int:user_id>/', views.admin_users_api, name='admin_user_detail'),
    path('admin-dashboard/api/users/<int:user_id>/toggle/', views.admin_toggle_user_api, name='admin_toggle_user'),
    path('admin-dashboard/api/logs/',           views.admin_logs_api,       name='admin_logs'),
    path('admin-dashboard/api/logs/export/',    views.admin_logs_export,    name='admin_logs_export'),
    path('admin-dashboard/api/govs/',           views.admin_govs_api,       name='admin_govs'),

    # ── AI APIs ───────────────────────────────────────────────────────
    path('api/ai/status/',                    ai_views.ai_status,           name='ai_status'),
    path('api/ai/chat/',                      ai_views.ai_chat,             name='ai_chat'),
    path('api/ai/classify/',                  ai_views.ai_classify,         name='ai_classify'),
    path('api/ai/report/',                    ai_views.ai_generate_report,  name='ai_report'),
    path('api/ai/analyze-image/',             ai_views.ai_analyze_image,    name='ai_analyze_image'),
    path('api/ai/duplicates/<int:pk>/',       ai_views.ai_detect_duplicates,name='ai_duplicates'),
]