"""
Receipt Service - PDF Generation and Email Sending for ReRoots
Uses ReportLab for PDF generation and SendGrid for email delivery
"""

import os
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# SendGrid import
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "support@reroots.ca")
SENDGRID_FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "ReRoots")


def generate_receipt_pdf(order: dict) -> bytes:
    """
    Generate a professional PDF receipt for an order.
    
    Args:
        order: Order document with items, shipping_address, totals, etc.
        
    Returns:
        bytes: PDF content as bytes
    """
    buffer = io.BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Define styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=6,
        textColor=colors.HexColor('#2D2A2E'),
        fontName='Helvetica-Bold',
        alignment=TA_CENTER
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#D4AF37'),
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica'
    )
    
    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#2D2A2E'),
        spaceBefore=15,
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        fontName='Helvetica'
    )
    
    small_style = ParagraphStyle(
        'Small',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        fontName='Helvetica'
    )
    
    # Build PDF elements
    elements = []
    
    # Header - Brand Name
    elements.append(Paragraph("REROOTS", title_style))
    elements.append(Paragraph("BEAUTY ENHANCER", subtitle_style))
    elements.append(Spacer(1, 10))
    
    # Receipt Title with Order Number
    receipt_title = ParagraphStyle(
        'ReceiptTitle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2D2A2E'),
        alignment=TA_CENTER,
        spaceAfter=5
    )
    elements.append(Paragraph("PAYMENT RECEIPT", receipt_title))
    elements.append(Paragraph(f"Order #{order.get('order_number', 'N/A')}", 
                              ParagraphStyle('OrderNum', parent=small_style, alignment=TA_CENTER)))
    elements.append(Spacer(1, 15))
    
    # Order Details Row
    order_date = order.get('created_at', datetime.now(timezone.utc).isoformat())
    if isinstance(order_date, str):
        try:
            order_date_parsed = datetime.fromisoformat(order_date.replace('Z', '+00:00'))
            order_date_formatted = order_date_parsed.strftime('%B %d, %Y')
        except (ValueError, AttributeError):
            order_date_formatted = order_date[:10] if len(order_date) >= 10 else 'N/A'
    else:
        order_date_formatted = order_date.strftime('%B %d, %Y') if order_date else 'N/A'
    
    order_info_data = [
        ['Order Date:', order_date_formatted],
        ['Payment Status:', 'PAID'],
        ['Payment Method:', order.get('payment_method', 'Credit Card').replace('_', ' ').title()],
    ]
    
    order_info_table = Table(order_info_data, colWidths=[1.5*inch, 3*inch])
    order_info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(order_info_table)
    elements.append(Spacer(1, 15))
    
    # Billing/Shipping Address
    elements.append(Paragraph("SHIPPING ADDRESS", section_header_style))
    
    shipping_addr = order.get('shipping_address', {})
    name = f"{shipping_addr.get('first_name', '')} {shipping_addr.get('last_name', '')}".strip() or "Customer"
    address_lines = [
        name,
        shipping_addr.get('address', '') or shipping_addr.get('address_line1', ''),
        f"{shipping_addr.get('city', '')}, {shipping_addr.get('province', '') or shipping_addr.get('state', '')} {shipping_addr.get('postal_code', '')}",
        shipping_addr.get('country', 'Canada')
    ]
    
    for line in address_lines:
        if line.strip():
            elements.append(Paragraph(line, normal_style))
    
    elements.append(Spacer(1, 15))
    
    # Order Items Table
    elements.append(Paragraph("ORDER ITEMS", section_header_style))
    
    # Table Header
    items_data = [['Product', 'Qty', 'Price', 'Total']]
    
    # Add items
    for item in order.get('items', []):
        product_name = item.get('product_name', item.get('name', 'Product'))
        # Truncate long names
        if len(product_name) > 40:
            product_name = product_name[:37] + '...'
        quantity = item.get('quantity', 1)
        price = float(item.get('price', 0))
        line_total = price * quantity
        
        items_data.append([
            product_name,
            str(quantity),
            f"${price:.2f}",
            f"${line_total:.2f}"
        ])
    
    items_table = Table(items_data, colWidths=[3.5*inch, 0.6*inch, 1*inch, 1*inch])
    items_table.setStyle(TableStyle([
        # Header style
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2D2A2E')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Body style
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#333333')),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E5E5')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FAFAFA')]),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 15))
    
    # Order Totals
    subtotal = float(order.get('subtotal', 0))
    shipping = float(order.get('shipping', 0))
    tax = float(order.get('tax', 0))
    discount = float(order.get('discount_amount', 0))
    total = float(order.get('total', subtotal + shipping + tax - discount))
    
    totals_data = [
        ['Subtotal:', f"${subtotal:.2f}"],
        ['Shipping:', f"${shipping:.2f}" if shipping > 0 else "FREE"],
        ['Tax (HST/GST):', f"${tax:.2f}"],
    ]
    
    if discount > 0:
        totals_data.append(['Discount:', f"-${discount:.2f}"])
    
    totals_data.append(['', ''])  # Spacer row
    totals_data.append(['TOTAL:', f"${total:.2f} CAD"])
    
    totals_table = Table(totals_data, colWidths=[5*inch, 1.1*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#2D2A2E')),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#2D2A2E')),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 25))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=small_style,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#888888')
    )
    
    elements.append(Paragraph("Thank you for shopping with ReRoots!", footer_style))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph("support@reroots.ca | www.reroots.ca", footer_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        "This is your official payment receipt. Please keep it for your records.",
        footer_style
    ))
    
    # Build the PDF
    doc.build(elements)
    
    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


async def send_receipt_email(order: dict, customer_email: str) -> bool:
    """
    Send PDF receipt via email using SendGrid.
    
    Args:
        order: Order document
        customer_email: Customer's email address
        
    Returns:
        bool: True if email sent successfully
    """
    if not SENDGRID_API_KEY:
        logging.info(f"[Receipt] SendGrid not configured - skipping email for order {order.get('order_number')}")
        return False
    
    if not customer_email:
        logging.warning(f"[Receipt] No email for order {order.get('order_number')}")
        return False
    
    try:
        import base64
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
        
        # Generate PDF
        pdf_bytes = generate_receipt_pdf(order)
        pdf_base64 = base64.b64encode(pdf_bytes).decode()
        
        order_number = order.get('order_number', 'N/A')
        customer_name = f"{order.get('shipping_address', {}).get('first_name', 'Customer')}"
        
        # Create email content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Your Receipt - ReRoots</title>
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #2D2A2E; margin: 0; padding: 0; background-color: #f5f5f5;">
            <table cellpadding="0" cellspacing="0" width="100%" style="background-color: #f5f5f5;">
                <tr>
                    <td align="center" style="padding: 20px;">
                        <table cellpadding="0" cellspacing="0" width="600" style="background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                            <tr>
                                <td style="background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); padding: 30px 20px; text-align: center;">
                                    <div style="font-size: 32px; font-weight: bold; color: #F8A5B8; letter-spacing: 2px;">REROOTS</div>
                                    <div style="color: #D4AF37; font-size: 12px; letter-spacing: 3px; margin-top: 5px;">BEAUTY ENHANCER</div>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 40px 30px;">
                                    <div style="text-align: center; margin-bottom: 30px;">
                                        <div style="font-size: 50px;">🧾</div>
                                    </div>
                                    
                                    <h1 style="text-align: center; color: #2D2A2E; margin: 0 0 10px 0; font-size: 24px;">Your Receipt is Ready</h1>
                                    <p style="text-align: center; color: #666; margin: 0 0 30px 0;">Hi {customer_name}, your payment receipt for Order #{order_number} is attached.</p>
                                    
                                    <div style="background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%); border-radius: 12px; padding: 25px; margin: 20px 0; text-align: center;">
                                        <div style="font-size: 14px; color: #2E7D32; text-transform: uppercase; letter-spacing: 1px;">Payment Confirmed</div>
                                        <div style="font-size: 28px; font-weight: bold; color: #2E7D32; margin: 10px 0;">${order.get('total', 0):.2f} CAD</div>
                                    </div>
                                    
                                    <div style="background: #f9f9f9; border-radius: 8px; padding: 20px; margin: 20px 0;">
                                        <p style="color: #666; margin: 0; font-size: 14px; text-align: center;">
                                            📎 Your PDF receipt is attached to this email.<br>
                                            Please save it for your records.
                                        </p>
                                    </div>
                                    
                                    <p style="text-align: center; color: #666; margin-top: 30px; font-size: 14px;">
                                        Questions? Contact us at <a href="mailto:support@reroots.ca" style="color: #F8A5B8;">support@reroots.ca</a>
                                    </p>
                                </td>
                            </tr>
                            <tr>
                                <td style="background: #2D2A2E; color: #ffffff; padding: 20px; text-align: center;">
                                    <p style="margin: 0; font-size: 12px; color: #888;">© 2025 ReRoots. All rights reserved.</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        
        # Create SendGrid message
        message = Mail(
            from_email=(SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME),
            to_emails=customer_email,
            subject=f"Your Receipt - Order #{order_number}",
            html_content=html_content
        )
        
        # Attach PDF
        attachment = Attachment()
        attachment.file_content = FileContent(pdf_base64)
        attachment.file_name = FileName(f"ReRoots_Receipt_{order_number}.pdf")
        attachment.file_type = FileType("application/pdf")
        attachment.disposition = Disposition("attachment")
        message.add_attachment(attachment)
        
        # Send email
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code in [200, 202]:
            logging.info(f"[Receipt] Email sent to {customer_email} for order {order_number}")
            return True
        else:
            logging.error(f"[Receipt] SendGrid error: {response.status_code}")
            return False
            
    except Exception as e:
        logging.error(f"[Receipt] Failed to send email: {e}")
        return False
