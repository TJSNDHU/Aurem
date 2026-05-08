"""
AUREM Invoice PDF Generator
============================
Generates professional PDF invoices using reportlab.
"""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER


def generate_invoice_pdf(invoice: dict, business_info: dict = None) -> bytes:
    """Generate a PDF invoice and return bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    elements = []

    biz = business_info or {}
    biz_name = biz.get("name", "AUREM Business Solutions")
    biz_email = biz.get("email", "")
    biz_phone = biz.get("phone", "")
    biz_address = biz.get("address", "")

    # Styles
    title_style = ParagraphStyle('InvoiceTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#1A1A2E'), spaceAfter=6)
    subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#888888'))
    heading_style = ParagraphStyle('Head', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#1A1A2E'), spaceBefore=16, spaceAfter=6)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#333333'))
    right_style = ParagraphStyle('Right', parent=styles['Normal'], fontSize=10, alignment=TA_RIGHT)
    bold_style = ParagraphStyle('Bold', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#1A1A2E'))

    # Header
    elements.append(Paragraph("INVOICE", title_style))
    elements.append(Paragraph(f"#{invoice.get('invoice_number', 'N/A')}", subtitle_style))
    elements.append(Spacer(1, 12))

    # Business + Customer info side by side
    info_data = [
        [
            Paragraph(f"<b>From:</b><br/>{biz_name}<br/>{biz_email}<br/>{biz_phone}<br/>{biz_address}", body_style),
            Paragraph(
                f"<b>Bill To:</b><br/>"
                f"{invoice.get('customer_name', '')}<br/>"
                f"{invoice.get('customer_email', '') or ''}<br/>"
                f"{invoice.get('customer_phone', '') or ''}",
                body_style
            ),
            Paragraph(
                f"<b>Invoice Date:</b><br/>{(invoice.get('created_at') or '')[:10]}<br/><br/>"
                f"<b>Due Date:</b><br/>{(invoice.get('due_date') or '')[:10]}<br/><br/>"
                f"<b>Status:</b> {(invoice.get('status') or 'draft').upper()}",
                body_style
            ),
        ]
    ]
    info_table = Table(info_data, colWidths=[2.5*inch, 2.5*inch, 2*inch])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))

    # Line items table
    elements.append(Paragraph("Line Items", heading_style))
    table_data = [['Description', 'Qty', 'Unit Price', 'Amount']]
    for item in invoice.get('line_items', []):
        table_data.append([
            item.get('description', ''),
            str(item.get('quantity', 1)),
            f"${item.get('unit_price', 0):.2f}",
            f"${item.get('amount', 0):.2f}",
        ])

    t = Table(table_data, colWidths=[3.5*inch, 0.8*inch, 1.1*inch, 1.1*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A1A2E')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, 0), 0.5, colors.HexColor('#1A1A2E')),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor('#dddddd')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 12))

    # Totals
    currency = invoice.get('currency', 'CAD')
    totals_data = [
        ['', 'Subtotal:', f"${invoice.get('subtotal', 0):.2f} {currency}"],
        ['', f"Tax ({invoice.get('tax_rate', 0)}%):", f"${invoice.get('tax_amount', 0):.2f}"],
        ['', 'Total:', f"${invoice.get('total', 0):.2f} {currency}"],
    ]
    if invoice.get('amount_paid', 0) > 0:
        totals_data.append(['', 'Paid:', f"-${invoice.get('amount_paid', 0):.2f}"])
        totals_data.append(['', 'Amount Due:', f"${invoice.get('amount_due', 0):.2f} {currency}"])

    totals = Table(totals_data, colWidths=[3.5*inch, 1.5*inch, 1.5*inch])
    totals.setStyle(TableStyle([
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (1, 2), (2, 2), 'Helvetica-Bold'),
        ('LINEABOVE', (1, 2), (2, 2), 1, colors.HexColor('#1A1A2E')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(totals)
    elements.append(Spacer(1, 20))

    # Payment instructions
    method = (invoice.get('payment_method', 'e_transfer') or 'e_transfer').replace('_', ' ').title()
    instructions = invoice.get('payment_instructions', '')
    if instructions:
        elements.append(Paragraph("Payment Instructions", heading_style))
        elements.append(Paragraph(f"<b>Method:</b> {method}", body_style))
        elements.append(Paragraph(instructions, body_style))
        elements.append(Spacer(1, 12))

    # Payment history
    payments = invoice.get('payments', [])
    if payments:
        elements.append(Paragraph("Payment History", heading_style))
        for p in payments:
            elements.append(Paragraph(
                f"${p.get('amount', 0):.2f} via {p.get('method', '').replace('_', ' ')} "
                f"{'(Ref: ' + p['reference'] + ')' if p.get('reference') else ''} "
                f"on {(p.get('recorded_at') or '')[:10]}",
                body_style
            ))
        elements.append(Spacer(1, 12))

    # Notes
    if invoice.get('notes'):
        elements.append(Paragraph("Notes", heading_style))
        elements.append(Paragraph(invoice['notes'], body_style))
        elements.append(Spacer(1, 12))

    # Footer
    elements.append(Spacer(1, 30))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#aaaaaa'), alignment=TA_CENTER)
    elements.append(Paragraph(f"Generated by AUREM AI Business Platform | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", footer_style))

    doc.build(elements)
    return buffer.getvalue()
