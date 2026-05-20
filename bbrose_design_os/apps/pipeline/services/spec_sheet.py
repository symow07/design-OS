import json
import os
from io import BytesIO

import requests
from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BBROSE_BLUSH = colors.HexColor('#F2C4CE')
BBROSE_ROSE_GOLD = colors.HexColor('#B5895A')
BBROSE_DARK = colors.HexColor('#1A1A1A')
BBROSE_CREAM = colors.HexColor('#F5EDD6')


def generate_spec_sheet(packaging_output):
    """
    Generate a BBROSE-branded PDF spec sheet for a PackagingOutput.
    Saves to packaging_output.spec_pdf field and returns the file content.
    """
    task = packaging_output.task
    product = task.product
    spec = packaging_output.spec_sheet
    image = packaging_output.approved_image

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle(
        'BBROSEHeading', fontSize=16, textColor=BBROSE_ROSE_GOLD,
        spaceAfter=4 * mm, fontName='Helvetica-Bold',
    )
    label_style = ParagraphStyle(
        'BBROSELabel', fontSize=9, textColor=BBROSE_ROSE_GOLD,
        fontName='Helvetica-Bold', spaceAfter=1 * mm,
    )
    body_style = ParagraphStyle(
        'BBROSEBody', fontSize=10, textColor=BBROSE_DARK,
        fontName='Helvetica', spaceAfter=3 * mm,
    )

    story = []

    story.append(Paragraph(
        'BBROSE DESIGN OS',
        ParagraphStyle('Header', fontSize=10, textColor=BBROSE_ROSE_GOLD, fontName='Helvetica-Bold'),
    ))
    story.append(Paragraph('Packaging Specification Sheet', heading_style))
    story.append(Spacer(1, 5 * mm))

    if product:
        story.append(Paragraph('PRODUCT', label_style))
        story.append(Paragraph(f'{product.name} ({product.product_id})', body_style))

    story.append(Paragraph('DIRECTION', label_style))
    story.append(Paragraph(image.direction_name, body_style))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('APPROVED DESIGN', label_style))
    img_url = image.image_url
    try:
        if image.image_file and os.path.exists(image.image_file.path):
            rl_img = RLImage(image.image_file.path, width=60 * mm, height=105 * mm)
        else:
            resp = requests.get(img_url, timeout=15)
            img_buffer = BytesIO(resp.content)
            rl_img = RLImage(img_buffer, width=60 * mm, height=105 * mm)
        story.append(rl_img)
    except Exception:
        story.append(Paragraph('[Image unavailable]', body_style))
    story.append(Spacer(1, 4 * mm))

    if spec.get('structure_type'):
        story.append(Paragraph('PACKAGING STRUCTURE', label_style))
        dims = spec.get('dimensions', {})
        dim_str = f"{dims.get('diameter', '?')} × {dims.get('height', '?')} {dims.get('units', 'mm')}"
        story.append(Paragraph(f"{spec['structure_type']} | {dim_str}", body_style))

    # Dieline backend: render the confirmed carton spec.
    if spec.get('backend') == 'dieline':
        story.append(Paragraph('DIELINE', label_style))
        cd = spec.get('confirmed_dimensions', {})
        template = spec.get('template', 'straight_tuck_end_carton').replace('_', ' ').title()
        story.append(Paragraph(
            f"{template} (Scenario {spec.get('scenario', '?')})", body_style))
        if cd:
            dieline_data = [
                ['Width', 'Depth', 'Height', 'Bleed', 'Safe', 'Glue tab'],
                [
                    f"{cd.get('width_mm', '?')}", f"{cd.get('depth_mm', '?')}",
                    f"{cd.get('height_mm', '?')}", f"{cd.get('bleed_mm', '?')}",
                    f"{cd.get('safe_margin_mm', '?')}", f"{cd.get('glue_tab_mm', '?')}",
                ],
            ]
            dieline_table = Table(dieline_data, colWidths=[28 * mm] * 6)
            dieline_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), BBROSE_BLUSH),
                ('TEXTCOLOR', (0, 0), (-1, 0), BBROSE_DARK),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D0D0D0')),
            ]))
            story.append(dieline_table)
        flat_w, flat_h = spec.get('flat_width_mm'), spec.get('flat_height_mm')
        if flat_w and flat_h:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(
                f"Flat size: {flat_w} × {flat_h} mm · {spec.get('panel_count', '?')} panels (all units mm)",
                body_style))
        story.append(Spacer(1, 4 * mm))

    palette = spec.get('color_codes', [])
    if palette:
        story.append(Paragraph('COLOUR SYSTEM', label_style))
        color_data = [['Role', 'Name', 'Hex', 'Pantone']]
        for swatch in palette:
            color_data.append([
                swatch.get('role', ''), swatch.get('name', ''),
                swatch.get('hex', ''), swatch.get('pantone', ''),
            ])
        color_table = Table(color_data, colWidths=[35 * mm, 45 * mm, 35 * mm, 40 * mm])
        color_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BBROSE_BLUSH),
            ('TEXTCOLOR', (0, 0), (-1, 0), BBROSE_DARK),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D0D0D0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [BBROSE_CREAM, colors.white]),
        ]))
        story.append(color_table)
        story.append(Spacer(1, 4 * mm))

    if spec.get('material'):
        story.append(Paragraph('MATERIAL & FINISH', label_style))
        story.append(Paragraph(spec['material'], body_style))

    story.append(Paragraph('QA REVIEW', label_style))
    try:
        qa = json.loads(image.qa_notes) if image.qa_notes else {}
        qa_text = f"Score: {qa.get('score', 'N/A')}/10 | {qa.get('recommendation', 'N/A').upper()}"
        if qa.get('issues'):
            qa_text += f" | Notes: {', '.join(qa['issues'])}"
    except Exception:
        qa_text = 'QA data unavailable'
    story.append(Paragraph(qa_text, body_style))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f"Approved: {timezone.now().strftime('%B %d, %Y %H:%M UTC')}",
        ParagraphStyle('Timestamp', fontSize=8, textColor=colors.HexColor('#999999')),
    ))

    doc.build(story)
    pdf_content = buffer.getvalue()

    filename = f"spec_sheet_task_{task.id}_{image.direction_name.replace(' ', '_')}.pdf"
    packaging_output.spec_pdf = ContentFile(pdf_content, name=filename)
    packaging_output.save(update_fields=['spec_pdf'])

    return pdf_content
