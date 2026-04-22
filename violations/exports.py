"""
أدوات تصدير التقارير — Excel و PDF
"""
import io
from datetime import datetime
import openpyxl
from openpyxl.styles import (Font, PatternFill, Alignment, Border, Side,
                              GradientFill)
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
import os


# ── COLUMN DEFINITIONS ─────────────────────────────────────────────────────
COLUMNS = [
    ('code',               'الرمز',                    12),
    ('governorate__name_ar','المحافظة',                 14),
    ('district_name',      'المركز',                   14),
    ('village',            'القرية / المدينة',          18),
    ('occupant',           'اسم المستغل',              20),
    ('basin',              'اسم الحوض',                22),
    ('description',        'وصف الاستغلال',            18),
    ('area_nile_bank',     'تعدي على الجسر م²',        14),
    ('area_public',        'تعدي على المنفعة م²',      14),
    ('area_outside',       'خارج الحياض م²',           13),
    ('area_total',         'المسطح الإجمالي م²',       16),
    ('status',             'الحالة',                    10),
]

STATUS_AR = {'approved': 'معتمد', 'pending': 'في الانتظار', 'rejected': 'مرفوض'}


# ══════════════════════════════════════════════════════════════════
# EXCEL EXPORT
# ══════════════════════════════════════════════════════════════════
def export_excel(records, filters=None, user=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'التعديات'
    ws.sheet_view.rightToLeft = True

    # ── Colors ──
    HDR_FILL  = PatternFill('solid', fgColor='0D3B6E')
    SUB_FILL  = PatternFill('solid', fgColor='1A6EA8')
    ALT_FILL  = PatternFill('solid', fgColor='EEF4FB')
    GRN_FILL  = PatternFill('solid', fgColor='D4EDDA')
    YEL_FILL  = PatternFill('solid', fgColor='FFF3CD')
    RED_FILL  = PatternFill('solid', fgColor='F8D7DA')
    thin = Side(style='thin', color='CCCCCC')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # ── Title Row ──
    ws.merge_cells('A1:L1')
    title_cell = ws['A1']
    title_cell.value = 'منظومة رصد التعديات على نهر النيل — وزارة الموارد المائية والري'
    title_cell.font  = Font(name='Arial', bold=True, size=14, color='FFFFFF')
    title_cell.fill  = HDR_FILL
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 30

    # ── Subtitle ──
    ws.merge_cells('A2:L2')
    sub = ws['A2']
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    filter_text = _build_filter_text(filters)
    sub.value = f'تاريخ التقرير: {now}  |  {filter_text}  |  إجمالي السجلات: {len(records)}'
    sub.font  = Font(name='Arial', size=10, color='FFFFFF')
    sub.fill  = SUB_FILL
    sub.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[2].height = 20

    # ── Headers ──
    ws.row_dimensions[3].height = 22
    for col_idx, (field, label, width) in enumerate(COLUMNS, 1):
        cell = ws.cell(row=3, column=col_idx, value=label)
        cell.font      = Font(name='Arial', bold=True, size=10, color='FFFFFF')
        cell.fill      = PatternFill('solid', fgColor='1A5276')
        cell.alignment = Alignment(horizontal='center', vertical='center',
                                   wrap_text=True)
        cell.border    = border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # ── Data Rows ──
    total_area = 0
    for row_idx, rec in enumerate(records, 4):
        fill = ALT_FILL if row_idx % 2 == 0 else PatternFill('solid', fgColor='FFFFFF')
        ws.row_dimensions[row_idx].height = 16

        for col_idx, (field, label, width) in enumerate(COLUMNS, 1):
            val = rec.get(field, '')
            if field == 'status':
                val = STATUS_AR.get(str(val), val)
                if rec.get('status') == 'approved':   fill = GRN_FILL if row_idx % 2 == 0 else PatternFill('solid', fgColor='ECFDF5')
                elif rec.get('status') == 'pending':  fill = YEL_FILL if row_idx % 2 == 0 else PatternFill('solid', fgColor='FFFDE7')
                elif rec.get('status') == 'rejected': fill = RED_FILL if row_idx % 2 == 0 else PatternFill('solid', fgColor='FFF5F5')
            if field in ('area_nile_bank','area_public','area_outside','area_total'):
                val = round(float(val or 0), 2)
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font      = Font(name='Arial', size=9)
            cell.alignment = Alignment(horizontal='center' if field.startswith('area') or field == 'code' or field == 'status'
                                       else 'right', vertical='center')
            cell.fill   = fill
            cell.border = border
        total_area += float(rec.get('area_total', 0) or 0)

    # ── Totals Row ──
    total_row = len(records) + 4
    ws.row_dimensions[total_row].height = 20
    ws.merge_cells(f'A{total_row}:J{total_row}')
    tot_label = ws[f'A{total_row}']
    tot_label.value = f'الإجمالي — {len(records)} سجل'
    tot_label.font  = Font(name='Arial', bold=True, size=10, color='FFFFFF')
    tot_label.fill  = HDR_FILL
    tot_label.alignment = Alignment(horizontal='center', vertical='center')
    tot_label.border = border

    tot_val = ws[f'K{total_row}']
    tot_val.value = round(total_area, 2)
    tot_val.font  = Font(name='Arial', bold=True, size=10, color='FFFFFF')
    tot_val.fill  = HDR_FILL
    tot_val.alignment = Alignment(horizontal='center', vertical='center')
    tot_val.border = border

    ws[f'L{total_row}'].fill = HDR_FILL
    ws[f'L{total_row}'].border = border

    # ── Summary Sheet ──
    ws2 = wb.create_sheet('ملخص إحصائي')
    ws2.sheet_view.rightToLeft = True
    _build_summary_sheet(ws2, records, HDR_FILL, SUB_FILL, border)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _build_summary_sheet(ws, records, hdr_fill, sub_fill, border):
    ws.column_dimensions['A'].width = 25
    ws.column_dimensions['B'].width = 18

    def hdr(row, text):
        ws.merge_cells(f'A{row}:B{row}')
        c = ws[f'A{row}']
        c.value = text
        c.font  = Font(name='Arial', bold=True, size=11, color='FFFFFF')
        c.fill  = hdr_fill
        c.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[row].height = 22

    def row2(ws, row, label, val):
        lc = ws.cell(row=row, column=1, value=label)
        vc = ws.cell(row=row, column=2, value=val)
        lc.font = Font(name='Arial', size=10)
        vc.font = Font(name='Arial', bold=True, size=10)
        lc.alignment = Alignment(horizontal='right')
        vc.alignment = Alignment(horizontal='center')
        lc.border = vc.border = border

    total = len(records)
    total_area = sum(float(r.get('area_total', 0) or 0) for r in records)

    hdr(1, 'ملخص إحصائي للتقرير')
    row2(ws, 2, 'إجمالي السجلات', total)
    row2(ws, 3, 'إجمالي المساحة م²', round(total_area, 2))
    row2(ws, 4, 'متوسط المساحة م²', round(total_area / total, 2) if total else 0)

    # By status
    hdr(6, 'توزيع الحالات')
    from collections import Counter
    statuses = Counter(r.get('status', '') for r in records)
    r = 7
    for s, cnt in statuses.items():
        row2(ws, r, STATUS_AR.get(s, s), cnt)
        r += 1

    # By gov
    hdr(r + 1, 'توزيع المحافظات')
    govs = Counter(r.get('governorate__name_ar', '—') for r in records)
    r += 2
    for g, cnt in govs.most_common():
        row2(ws, r, g, cnt)
        r += 1

    # By description
    hdr(r + 1, 'أنواع الاستغلال (أعلى 10)')
    descs = Counter(r.get('description', '') for r in records)
    r += 2
    for d, cnt in descs.most_common(10):
        row2(ws, r, d[:40], cnt)
        r += 1


def _build_filter_text(filters):
    if not filters:
        return 'جميع البيانات'
    parts = []
    mapping = {
        'gov': 'المحافظة', 'district': 'المركز', 'village': 'القرية',
        'description': 'وصف الاستغلال', 'min_area': 'الحد الأدنى للمساحة',
        'search': 'بحث', 'status': 'الحالة',
    }
    for k, v in filters.items():
        if v:
            parts.append(f"{mapping.get(k, k)}: {v}")
    return ' | '.join(parts) if parts else 'جميع البيانات'


# ══════════════════════════════════════════════════════════════════
# PDF EXPORT
# ══════════════════════════════════════════════════════════════════
def export_pdf(records, filters=None, user=None):
    buf = io.BytesIO()

    # Register Arabic font if available
    font_name = 'Helvetica'  # fallback
    arabic_font_paths = [
        '/usr/share/fonts/truetype/arabic/ae_AlArabiya.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    ]
    for fp in arabic_font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('Arabic', fp))
                font_name = 'Arabic'
                break
            except Exception:
                pass

    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title='تقرير التعديات على نهر النيل',
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ArabicTitle', fontName=font_name, fontSize=14,
        textColor=colors.HexColor('#0D3B6E'),
        alignment=TA_CENTER, spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        'ArabicSub', fontName=font_name, fontSize=9,
        textColor=colors.grey, alignment=TA_CENTER, spaceAfter=12,
    )
    normal_style = ParagraphStyle(
        'ArabicNormal', fontName=font_name, fontSize=8,
        alignment=TA_RIGHT,
    )

    elements = []

    # Title
    elements.append(Paragraph('منظومة رصد التعديات على نهر النيل', title_style))
    elements.append(Paragraph('وزارة الموارد المائية والري — جمهورية مصر العربية', subtitle_style))
    elements.append(HRFlowable(width='100%', thickness=2,
                                color=colors.HexColor('#0D3B6E'), spaceAfter=8))

    # Meta info
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    filter_text = _build_filter_text(filters)
    meta = f'تاريخ: {now}   |   {filter_text}   |   عدد السجلات: {len(records)}'
    elements.append(Paragraph(meta, subtitle_style))
    elements.append(Spacer(1, 0.3*cm))

    # Table headers
    headers = [col[1] for col in COLUMNS]

    # Table data
    data = [headers]
    total_area = 0
    for rec in records:
        row = []
        for field, label, width in COLUMNS:
            val = rec.get(field, '') or ''
            if field == 'status':
                val = STATUS_AR.get(str(val), val)
            elif field in ('area_nile_bank','area_public','area_outside','area_total'):
                val = f"{float(val or 0):.1f}"
            row.append(str(val)[:30])
        data.append(row)
        total_area += float(rec.get('area_total', 0) or 0)

    # Totals row
    totals = ['الإجمالي'] + [''] * 9 + [f'{total_area:.1f}', '']
    data.append(totals)

    # Column widths proportional
    col_widths = [
        1.5*cm, 2.2*cm, 2.2*cm, 2.8*cm, 3.2*cm,
        3.5*cm, 2.8*cm, 2.0*cm, 2.0*cm, 2.0*cm,
        2.2*cm, 1.6*cm,
    ]

    table = Table(data, colWidths=col_widths, repeatRows=1)

    # Style
    primary   = colors.HexColor('#0D3B6E')
    secondary = colors.HexColor('#1A6EA8')
    alt_row   = colors.HexColor('#EEF4FB')

    style = TableStyle([
        # Header
        ('BACKGROUND',  (0,0), (-1,0),  primary),
        ('TEXTCOLOR',   (0,0), (-1,0),  colors.white),
        ('FONTNAME',    (0,0), (-1,0),  font_name),
        ('FONTSIZE',    (0,0), (-1,0),  7.5),
        ('ALIGN',       (0,0), (-1,0),  'CENTER'),
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUND',(0,1),(-1,-2), [colors.white, alt_row]),
        ('FONTNAME',    (0,1), (-1,-1), font_name),
        ('FONTSIZE',    (0,1), (-1,-1), 7),
        ('ALIGN',       (0,1), (-1,-1), 'CENTER'),
        ('GRID',        (0,0), (-1,-1), 0.4, colors.HexColor('#CCCCCC')),
        ('ROWHEIGHT',   (0,0), (-1,-1), 14),
        # Totals row
        ('BACKGROUND',  (0,-1), (-1,-1), primary),
        ('TEXTCOLOR',   (0,-1), (-1,-1), colors.white),
        ('FONTNAME',    (0,-1), (-1,-1), font_name),
        ('FONTSIZE',    (0,-1), (-1,-1), 8),
        ('FONTWEIGHT',  (0,-1), (-1,-1), 'BOLD'),
    ])
    table.setStyle(style)
    elements.append(table)

    # Footer summary
    elements.append(Spacer(1, 0.5*cm))
    elements.append(HRFlowable(width='100%', thickness=1,
                                color=colors.HexColor('#CCCCCC'), spaceAfter=6))
    summary_text = (f'إجمالي المساحة المتعدى عليها: {total_area:,.2f} م²   |   '
                    f'عدد السجلات: {len(records)}')
    elements.append(Paragraph(summary_text, subtitle_style))

    doc.build(elements)
    buf.seek(0)
    return buf
