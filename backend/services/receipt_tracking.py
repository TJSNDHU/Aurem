"""
ReRoots Receipt & Tracking Service
===================================

Generates PDF receipts and handles order tracking.
"""

import os
import io
import base64
from datetime import datetime, timezone
from typing import Dict, Optional
import httpx

# PDF Generation
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# FlagShip API Configuration
FLAGSHIP_API_TOKEN = os.environ.get("FLAGSHIP_API_TOKEN")
FLAGSHIP_API_URL = os.environ.get("FLAGSHIP_API_URL", "https://api.smartship.io")


# ============ COURIER SLIP / LABEL FETCHING ============

async def get_flagship_label(shipment_id: str) -> Dict:
    """
    Fetch shipping label from FlagShip after shipment is created.
    Returns both regular PDF and thermal printer formats.
    """
    if not FLAGSHIP_API_TOKEN:
        return {"success": False, "error": "FLAGSHIP_API_TOKEN not configured"}
    
    headers = {
        "X-Smartship-Token": FLAGSHIP_API_TOKEN,
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{FLAGSHIP_API_URL}/ship/shipments/{shipment_id}/labels",
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                label_data = response.json()
                content = label_data.get("content", label_data)
                return {
                    "success": True,
                    "label_url": content.get("labels", {}).get("regular", content.get("regular")),
                    "thermal_url": content.get("labels", {}).get("thermal", content.get("thermal")),
                    "zpl_url": content.get("labels", {}).get("zpl")  # For Zebra printers
                }
            else:
                return {
                    "success": False, 
                    "error": response.json() if response.content else response.text
                }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============ PAYMENT RECEIPT PDF GENERATOR ============

def generate_receipt_pdf(order: Dict) -> bytes:
    """
    Generates a branded ReRoots payment receipt PDF.
    Returns PDF as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        name='BrandTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='SubHeader',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor("#666666"),
        spaceAfter=20
    ))
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor("#1a1a2e"),
        spaceBefore=15,
        spaceAfter=8
    ))
    
    elements = []
    
    # ─── Header ───
    elements.append(Paragraph("ReRoots Aesthetics Inc.", styles["BrandTitle"]))
    elements.append(Paragraph(
        "7221 Sigsbee Drive, Mississauga, ON L4T3L6 | www.reroots.ca | support@reroots.ca",
        styles["SubHeader"]
    ))
    
    # ─── Receipt Title ───
    elements.append(Paragraph("PAYMENT RECEIPT", styles["Heading1"]))
    elements.append(Spacer(1, 10))
    
    # Order info
    order_id = order.get("order_id") or order.get("order_number") or order.get("id", "N/A")
    created_at = order.get("created_at", datetime.now(timezone.utc).isoformat())
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%B %d, %Y")
        except:
            created_at = str(created_at)[:10]
    
    elements.append(Paragraph(f"<b>Order #:</b> {order_id}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Date:</b> {created_at}", styles["Normal"]))
    elements.append(Spacer(1, 15))
    
    # ─── Customer Info ───
    elements.append(Paragraph("Bill To:", styles["SectionHeader"]))
    
    # Handle nested shipping_address or flat structure
    shipping = order.get("shipping_address", {})
    if isinstance(shipping, dict):
        customer_name = f"{shipping.get('first_name', '')} {shipping.get('last_name', '')}".strip()
        address = shipping.get("address_line1", shipping.get("address", ""))
        city = shipping.get("city", "")
        province = shipping.get("province", shipping.get("state", ""))
        postal = shipping.get("postal_code", "")
        email = shipping.get("email", order.get("email", order.get("customer_email", "")))
    else:
        customer_name = order.get("customer_name", "Customer")
        address = order.get("shipping_address", "")
        city = order.get("shipping_city", "")
        province = order.get("shipping_province", "")
        postal = order.get("shipping_postal_code", "")
        email = order.get("customer_email", order.get("email", ""))
    
    customer_name = customer_name or order.get("customer_name", "Customer")
    
    elements.append(Paragraph(customer_name, styles["Normal"]))
    if email:
        elements.append(Paragraph(email, styles["Normal"]))
    if address:
        elements.append(Paragraph(address, styles["Normal"]))
    if city or province or postal:
        elements.append(Paragraph(f"{city}, {province} {postal}", styles["Normal"]))
    elements.append(Spacer(1, 15))
    
    # ─── Order Items Table ───
    elements.append(Paragraph("Order Details:", styles["SectionHeader"]))
    
    table_data = [["Product", "Qty", "Price", "Total"]]
    
    items = order.get("items", order.get("line_items", []))
    subtotal = 0
    
    for item in items:
        name = item.get("name", item.get("title", "Product"))
        qty = item.get("quantity", 1)
        price = float(item.get("price", item.get("unit_price", 0)))
        item_total = qty * price
        subtotal += item_total
        
        table_data.append([
            name[:40] + "..." if len(name) > 40 else name,
            str(qty),
            f"${price:.2f}",
            f"${item_total:.2f}"
        ])
    
    # Calculate totals
    order_subtotal = float(order.get("subtotal", subtotal))
    shipping_cost = float(order.get("shipping_cost", order.get("shipping", 0)))
    tax = float(order.get("tax", order.get("tax_amount", 0)))
    discount = float(order.get("discount", order.get("discount_amount", 0)))
    total = float(order.get("total", order_subtotal + shipping_cost + tax - discount))
    
    # Add totals rows
    table_data.append(["", "", "Subtotal:", f"${order_subtotal:.2f}"])
    if discount > 0:
        table_data.append(["", "", "Discount:", f"-${discount:.2f}"])
    table_data.append(["", "", "Shipping:", f"${shipping_cost:.2f}"])
    table_data.append(["", "", "Tax (HST 13%):", f"${tax:.2f}"])
    table_data.append(["", "", "TOTAL:", f"${total:.2f} CAD"])
    
    # Create table
    table = Table(table_data, colWidths=[250, 50, 100, 100])
    table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        
        # Data rows
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -6), [colors.white, colors.HexColor("#f8f8f8")]),
        
        # Totals rows
        ("FONTNAME", (2, -5), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (2, -5), (-1, -5), 1, colors.HexColor("#dddddd")),
        ("LINEABOVE", (2, -1), (-1, -1), 2, colors.HexColor("#1a1a2e")),
        ("FONTSIZE", (2, -1), (-1, -1), 11),
        
        # Grid for items only
        ("GRID", (0, 0), (-1, -6), 0.5, colors.HexColor("#eeeeee")),
        
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # ─── Tracking Info ───
    tracking = order.get("tracking_number")
    if tracking:
        elements.append(Paragraph("Shipping Information:", styles["SectionHeader"]))
        elements.append(Paragraph(f"<b>Tracking Number:</b> {tracking}", styles["Normal"]))
        elements.append(Paragraph(
            f"<b>Track Your Order:</b> <a href='https://reroots.ca/track?order={order_id}'>reroots.ca/track?order={order_id}</a>",
            styles["Normal"]
        ))
        elements.append(Spacer(1, 15))
    
    # ─── Loyalty Points ───
    points_earned = order.get("points_earned", order.get("loyalty_points_earned", 0))
    points_redeemed = order.get("points_redeemed", order.get("loyalty_points_used", 0))
    if points_earned > 0 or points_redeemed > 0:
        elements.append(Paragraph("Roots Loyalty:", styles["SectionHeader"]))
        if points_earned > 0:
            elements.append(Paragraph(f"✨ You earned <b>{points_earned} Roots</b> with this order!", styles["Normal"]))
        if points_redeemed > 0:
            elements.append(Paragraph(f"💚 You redeemed <b>{points_redeemed} Roots</b> (saved ${points_redeemed * 0.05:.2f})", styles["Normal"]))
        elements.append(Spacer(1, 15))
    
    # ─── Footer ───
    elements.append(Spacer(1, 20))
    footer_style = ParagraphStyle(
        name='Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor("#888888"),
        alignment=1  # Center
    )
    elements.append(Paragraph(
        "Thank you for choosing ReRoots! 🌿<br/>"
        "Questions? Contact us at support@reroots.ca or WhatsApp us.<br/>"
        "www.reroots.ca",
        footer_style
    ))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


async def send_receipt_email(order: Dict, pdf_bytes: bytes, db) -> Dict:
    """
    Sends receipt via SendGrid with PDF attached.
    """
    import sendgrid
    from sendgrid.helpers.mail import (
        Mail, Attachment, FileContent, FileName,
        FileType, Disposition
    )
    
    sendgrid_key = os.environ.get("SENDGRID_API_KEY")
    if not sendgrid_key:
        return {"success": False, "error": "SENDGRID_API_KEY not configured"}
    
    # Get customer info
    shipping = order.get("shipping_address", {})
    if isinstance(shipping, dict):
        customer_name = f"{shipping.get('first_name', '')} {shipping.get('last_name', '')}".strip()
        customer_email = shipping.get("email", order.get("email", order.get("customer_email", "")))
    else:
        customer_name = order.get("customer_name", "Customer")
        customer_email = order.get("customer_email", order.get("email", ""))
    
    if not customer_email:
        return {"success": False, "error": "No customer email found"}
    
    order_id = order.get("order_id") or order.get("order_number") or order.get("id", "N/A")
    total = float(order.get("total", 0))
    tracking = order.get("tracking_number", "Will be updated shortly")
    first_name = customer_name.split()[0] if customer_name else "there"
    
    try:
        sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
        
        message = Mail(
            from_email=("orders@reroots.ca", "ReRoots"),
            to_emails=customer_email,
            subject=f"Your ReRoots Order #{order_id} — Receipt & Tracking",
            html_content=f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #ffffff;">
                <div style="background: linear-gradient(135deg, #1a1a2e 0%, #2d2d44 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">ReRoots</h1>
                    <p style="color: #F8A5B8; margin: 5px 0 0 0;">Biotech Skincare</p>
                </div>
                
                <div style="padding: 30px;">
                    <h2 style="color: #1a1a2e; margin-top: 0;">Thank you, {first_name}! 🌿</h2>
                    <p style="color: #444; line-height: 1.6;">
                        Your ReRoots order has been confirmed and is being prepared for shipment.
                        Your receipt is attached to this email.
                    </p>
                    
                    <div style="background: #f8f8f8; padding: 20px; border-radius: 12px; margin: 25px 0;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #666;">Order #:</td>
                                <td style="padding: 8px 0; text-align: right; font-weight: bold; color: #1a1a2e;">{order_id}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #666;">Total:</td>
                                <td style="padding: 8px 0; text-align: right; font-weight: bold; color: #1a1a2e;">${total:.2f} CAD</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #666;">Tracking:</td>
                                <td style="padding: 8px 0; text-align: right; font-weight: bold; color: #1a1a2e;">{tracking}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://reroots.ca/track?order={order_id}"
                           style="background: #1a1a2e; color: white; padding: 14px 28px; 
                                  border-radius: 8px; text-decoration: none; display: inline-block;
                                  font-weight: bold; margin-right: 10px;">
                            Track Your Order
                        </a>
                        <a href="https://reroots.ca/receipt/{order_id}"
                           style="background: #4CAF50; color: white; padding: 14px 28px; 
                                  border-radius: 8px; text-decoration: none; display: inline-block;
                                  font-weight: bold;">
                            Download Receipt
                        </a>
                    </div>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    
                    <p style="color: #888; font-size: 13px; text-align: center; line-height: 1.6;">
                        Questions? Reply to this email or 
                        <a href="https://wa.me/16475551234" style="color: #25d366;">WhatsApp us</a>.<br>
                        <strong>ReRoots Aesthetics Team</strong><br>
                        www.reroots.ca
                    </p>
                </div>
            </div>
            """
        )
        
        # Attach PDF
        encoded = base64.b64encode(pdf_bytes).decode()
        attachment = Attachment(
            FileContent(encoded),
            FileName(f"ReRoots_Receipt_{order_id}.pdf"),
            FileType("application/pdf"),
            Disposition("attachment")
        )
        message.attachment = attachment
        
        response = sg.send(message)
        
        # Log email sent
        if db is not None:
            await db.email_log.insert_one({
                "type": "receipt",
                "to": customer_email,
                "order_id": order_id,
                "status": "sent",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
        return {"success": True, "status_code": response.status_code}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============ LIVE TRACKING ============

async def get_tracking_status(shipment_id: str, tracking_number: str = None) -> Dict:
    """
    Fetches live tracking status from FlagShip.
    """
    if not FLAGSHIP_API_TOKEN:
        return {"success": False, "error": "FLAGSHIP_API_TOKEN not configured"}
    
    headers = {
        "X-Smartship-Token": FLAGSHIP_API_TOKEN,
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # Try by shipment ID first
            if shipment_id:
                response = await client.get(
                    f"{FLAGSHIP_API_URL}/ship/shipments/{shipment_id}/tracking",
                    headers=headers,
                    timeout=30.0
                )
            # Fallback to tracking number
            elif tracking_number:
                response = await client.get(
                    f"{FLAGSHIP_API_URL}/ship/tracking/{tracking_number}",
                    headers=headers,
                    timeout=30.0
                )
            else:
                return {"success": False, "error": "No shipment ID or tracking number provided"}
            
            if response.status_code == 200:
                tracking = response.json()
                content = tracking.get("content", tracking)
                
                return {
                    "success": True,
                    "status": content.get("status", "unknown"),
                    "estimated_delivery": content.get("estimated_delivery"),
                    "events": content.get("events", content.get("tracking_events", [])),
                    "courier": content.get("courier_name", content.get("courier")),
                    "service": content.get("service_name"),
                    "delivered_at": content.get("delivered_at")
                }
            else:
                return {
                    "success": False,
                    "error": response.json() if response.content else "Tracking not available"
                }
                
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_order_tracking(db, order_id: str) -> Dict:
    """
    Get tracking info for an order by order ID.
    Combines database info with live FlagShip tracking.
    """
    # Find order
    order = await db.orders.find_one({"order_id": order_id})
    if not order:
        order = await db.orders.find_one({"order_number": order_id})
    if not order:
        # Try by tracking number directly
        order = await db.orders.find_one({"tracking_number": order_id})
    
    if not order:
        return {"success": False, "error": "Order not found"}
    
    shipment_id = order.get("flagship_shipment_id")
    tracking_number = order.get("tracking_number")
    
    # Basic order info
    result = {
        "success": True,
        "order_id": order.get("order_id") or order.get("order_number"),
        "tracking_number": tracking_number,
        "courier": order.get("shipping_carrier", order.get("courier", "Unknown")),
        "status": order.get("status", order.get("order_status", "processing")),
        "created_at": order.get("created_at"),
        "shipped_at": order.get("shipped_at"),
        "events": []
    }
    
    # If we have a shipment ID or tracking, get live status
    if shipment_id or tracking_number:
        live_tracking = await get_tracking_status(shipment_id, tracking_number)
        
        if live_tracking.get("success"):
            result["status"] = live_tracking.get("status", result["status"])
            result["estimated_delivery"] = live_tracking.get("estimated_delivery")
            result["events"] = live_tracking.get("events", [])
            result["courier"] = live_tracking.get("courier", result["courier"])
            result["delivered_at"] = live_tracking.get("delivered_at")
    
    # Generate tracking URL based on courier
    carrier = result["courier"].lower().replace(" ", "_")
    tracking_urls = {
        "canada_post": f"https://www.canadapost-postescanada.ca/track-reperage/en#/search?searchFor={tracking_number}",
        "fedex": f"https://www.fedex.com/apps/fedextrack/?trknbr={tracking_number}",
        "purolator": f"https://www.purolator.com/purolator/ship-track/tracking-summary.page?pin={tracking_number}",
        "ups": f"https://www.ups.com/track?tracknum={tracking_number}",
        "canpar": f"https://www.canpar.com/en/track/TrackingAction.do?reference={tracking_number}",
    }
    result["tracking_url"] = tracking_urls.get(carrier, f"https://reroots.ca/track?order={result['order_id']}")
    
    return result
