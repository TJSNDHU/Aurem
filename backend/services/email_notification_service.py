"""
Email Notification Service
Sends email notifications for leads, alerts, and system events

Uses Resend for email delivery
"""

import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Import Resend (already installed in the project)
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("[EmailNotification] Resend not available")


async def send_lead_notification_email(to_email: str, lead_data: Dict) -> bool:
    """
    Send email notification to business owner about new lead
    
    Args:
        to_email: Recipient email address
        lead_data: Lead information
            {
                "lead_id": str,
                "name": str,
                "phone": str,
                "email": str,
                "intent_type": str,
                "value_estimate": float,
                "captured_at": str
            }
    
    Returns:
        Success boolean
    """
    if not RESEND_AVAILABLE:
        logger.warning("[EmailNotification] Resend not available, skipping email")
        return False
    
    try:
        # Get Resend API key
        resend_api_key = os.environ.get("RESEND_API_KEY")
        
        if not resend_api_key:
            logger.warning("[EmailNotification] RESEND_API_KEY not set")
            # For development: log the email instead
            logger.info(f"[EmailNotification] Would send to {to_email}: New lead {lead_data['name']}")
            return True  # Return success in dev mode
        
        resend.api_key = resend_api_key
        
        # Create email content
        subject = f"🎯 New Lead Captured: {lead_data['name']}"
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                           color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
                .lead-info {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .info-row {{ display: flex; margin: 10px 0; }}
                .label {{ font-weight: bold; width: 150px; color: #667eea; }}
                .value {{ flex: 1; }}
                .cta-button {{ background: #667eea; color: white; padding: 12px 30px; 
                               text-decoration: none; border-radius: 6px; display: inline-block; 
                               margin: 20px 0; }}
                .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎯 New Lead Captured!</h1>
                    <p>AUREM AI just captured a potential customer for you</p>
                </div>
                
                <div class="content">
                    <p>Great news! Your AI Agent detected a high-intent customer and automatically captured their information.</p>
                    
                    <div class="lead-info">
                        <h3>Lead Information</h3>
                        
                        <div class="info-row">
                            <div class="label">Name:</div>
                            <div class="value">{lead_data['name']}</div>
                        </div>
                        
                        <div class="info-row">
                            <div class="label">Phone:</div>
                            <div class="value">{lead_data['phone']}</div>
                        </div>
                        
                        <div class="info-row">
                            <div class="label">Email:</div>
                            <div class="value">{lead_data['email']}</div>
                        </div>
                        
                        <div class="info-row">
                            <div class="label">Intent:</div>
                            <div class="value"><strong>{lead_data['intent_type'].title()}</strong></div>
                        </div>
                        
                        <div class="info-row">
                            <div class="label">Estimated Value:</div>
                            <div class="value">${lead_data['value_estimate']:.2f}</div>
                        </div>
                        
                        <div class="info-row">
                            <div class="label">Captured:</div>
                            <div class="value">{lead_data['captured_at']}</div>
                        </div>
                    </div>
                    
                    <p><strong>💡 Next Steps:</strong></p>
                    <ul>
                        <li>Review the full conversation in your dashboard</li>
                        <li>Reach out to the customer within 24 hours for best conversion</li>
                        <li>Use the AI's insights to personalize your approach</li>
                    </ul>
                    
                    <center>
                        <a href="https://app.aurem.ai/leads/{lead_data['lead_id']}" class="cta-button">
                            View Lead Details →
                        </a>
                    </center>
                    
                    <div class="footer">
                        <p>This is an automated notification from AUREM AI</p>
                        <p>Lead ID: {lead_data['lead_id']}</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Send email via Resend
        response = resend.Emails.send({
            "from": "AUREM AI <leads@aurem.ai>",
            "to": to_email,
            "subject": subject,
            "html": html_content
        })
        
        logger.info(f"[EmailNotification] ✓ Email sent to {to_email} (ID: {response.get('id')})")
        return True
    
    except Exception as e:
        logger.error(f"[EmailNotification] Error sending email: {e}")
        return False


async def send_appointment_confirmation_email(
    to_email: str,
    appointment_data: Dict
) -> bool:
    """
    Send appointment confirmation email to customer
    
    Args:
        to_email: Customer email
        appointment_data: Appointment details
            {
                "customer_name": str,
                "service": str,
                "date": str,
                "time": str,
                "business_name": str,
                "calendar_link": str (optional)
            }
    
    Returns:
        Success boolean
    """
    if not RESEND_AVAILABLE:
        return False
    
    try:
        resend_api_key = os.environ.get("RESEND_API_KEY")
        
        if not resend_api_key:
            logger.info(f"[EmailNotification] Would send appointment confirmation to {to_email}")
            return True
        
        resend.api_key = resend_api_key
        
        subject = f"✅ Appointment Confirmed - {appointment_data['service']}"
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #10b981; color: white; padding: 30px; text-align: center; 
                           border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
                .appointment-box {{ background: white; padding: 20px; border-radius: 8px; 
                                    margin: 20px 0; border-left: 4px solid #10b981; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Appointment Confirmed</h1>
                </div>
                
                <div class="content">
                    <p>Hi {appointment_data['customer_name']},</p>
                    
                    <p>Your appointment has been confirmed! We look forward to seeing you.</p>
                    
                    <div class="appointment-box">
                        <h3>Appointment Details</h3>
                        <p><strong>Service:</strong> {appointment_data['service']}</p>
                        <p><strong>Date:</strong> {appointment_data['date']}</p>
                        <p><strong>Time:</strong> {appointment_data['time']}</p>
                        <p><strong>Business:</strong> {appointment_data['business_name']}</p>
                    </div>
                    
                    {f'<p><a href="{appointment_data["calendar_link"]}">Add to Calendar</a></p>' if appointment_data.get("calendar_link") else ""}
                    
                    <p>If you need to reschedule or have any questions, please reply to this email.</p>
                    
                    <p>See you soon!<br>- {appointment_data['business_name']} Team</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        response = resend.Emails.send({
            "from": f"{appointment_data['business_name']} <appointments@aurem.ai>",
            "to": to_email,
            "subject": subject,
            "html": html_content
        })
        
        logger.info(f"[EmailNotification] ✓ Appointment confirmation sent to {to_email}")
        return True
    
    except Exception as e:
        logger.error(f"[EmailNotification] Error sending confirmation: {e}")
        return False



async def send_panic_alert_email(to_email: str, alert_data: Dict) -> bool:
    """
    Send URGENT panic alert email to business owner
    
    Args:
        to_email: Business owner email
        alert_data: Panic event information
            {
                "business_name": str,
                "customer_name": str,
                "customer_phone": str,
                "customer_email": str,
                "trigger_reason": str,
                "sentiment_score": float,
                "detected_keywords": List[str],
                "last_message": str,
                "conversation_id": str,
                "event_id": str,
                "dashboard_link": str
            }
    
    Returns:
        Success boolean
    """
    if not RESEND_AVAILABLE:
        logger.warning("[EmailNotification] Resend not available, skipping panic alert email")
        return False
    
    try:
        resend_api_key = os.environ.get("RESEND_API_KEY")
        
        if not resend_api_key:
            logger.warning("[EmailNotification] RESEND_API_KEY not set")
            # For development: log the email
            logger.info(f"[EmailNotification] 🚨 PANIC ALERT would send to {to_email}: Customer {alert_data['customer_name']} needs attention")
            return True  # Return success in dev mode
        
        resend.api_key = resend_api_key
        
        # Create URGENT email content
        subject = f"🚨 URGENT: Customer Needs Attention - {alert_data['customer_name']}"
        
        # Format keywords
        keywords_html = ", ".join(alert_data.get("detected_keywords", [])[:5])
        if not keywords_html:
            keywords_html = "N/A"
        
        # Sentiment indicator
        sentiment_score = alert_data.get("sentiment_score", 0.0)
        if sentiment_score < -0.7:
            sentiment_indicator = "🔴 Very Negative"
            sentiment_color = "#dc2626"
        elif sentiment_score < -0.3:
            sentiment_indicator = "🟡 Concerned"
            sentiment_color = "#f59e0b"
        else:
            sentiment_indicator = "🟢 Neutral"
            sentiment_color = "#10b981"
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .alert-header {{ background: #dc2626; color: white; padding: 30px; 
                                 text-align: center; border-radius: 8px 8px 0 0; }}
                .alert-header h1 {{ margin: 0; font-size: 28px; }}
                .alert-icon {{ font-size: 48px; margin-bottom: 10px; }}
                .content {{ background: #fff; padding: 30px; border: 3px solid #dc2626; 
                           border-radius: 0 0 8px 8px; }}
                .customer-info {{ background: #fef2f2; padding: 20px; border-radius: 8px; 
                                 border-left: 4px solid #dc2626; margin: 20px 0; }}
                .info-row {{ display: flex; margin: 12px 0; }}
                .label {{ font-weight: bold; width: 150px; color: #dc2626; }}
                .value {{ flex: 1; }}
                .message-box {{ background: #f3f4f6; padding: 15px; border-radius: 6px; 
                               margin: 20px 0; font-style: italic; border-left: 4px solid #dc2626; }}
                .cta-button {{ background: #dc2626; color: white; padding: 15px 40px; 
                              text-decoration: none; border-radius: 6px; display: inline-block; 
                              margin: 20px 0; font-weight: bold; font-size: 16px; }}
                .cta-button:hover {{ background: #b91c1c; }}
                .urgent-banner {{ background: #fef2f2; padding: 15px; border-radius: 6px; 
                                 text-align: center; font-weight: bold; color: #dc2626; 
                                 border: 2px solid #dc2626; margin-bottom: 20px; }}
                .sentiment-badge {{ display: inline-block; padding: 8px 16px; border-radius: 20px; 
                                   font-size: 14px; font-weight: bold; color: white; }}
                .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 30px; 
                          padding-top: 20px; border-top: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="alert-header">
                    <div class="alert-icon">🚨</div>
                    <h1>Customer Needs Immediate Attention</h1>
                    <p style="margin: 10px 0 0 0; font-size: 16px;">AI detected potential issue requiring human intervention</p>
                </div>
                
                <div class="content">
                    <div class="urgent-banner">
                        ⚡ ACTION REQUIRED: This customer may need immediate support
                    </div>
                    
                    <div class="customer-info">
                        <h2 style="margin-top: 0; color: #dc2626;">Customer Information</h2>
                        <div class="info-row">
                            <span class="label">Name:</span>
                            <span class="value">{alert_data['customer_name']}</span>
                        </div>
                        <div class="info-row">
                            <span class="label">Phone:</span>
                            <span class="value">{alert_data['customer_phone']}</span>
                        </div>
                        <div class="info-row">
                            <span class="label">Email:</span>
                            <span class="value">{alert_data['customer_email']}</span>
                        </div>
                    </div>
                    
                    <h3>Alert Details</h3>
                    <div class="info-row">
                        <span class="label">Trigger Reason:</span>
                        <span class="value">{alert_data['trigger_reason']}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Sentiment:</span>
                        <span class="value">
                            <span class="sentiment-badge" style="background: {sentiment_color};">
                                {sentiment_indicator} ({sentiment_score:.2f})
                            </span>
                        </span>
                    </div>
                    <div class="info-row">
                        <span class="label">Detected Keywords:</span>
                        <span class="value">{keywords_html}</span>
                    </div>
                    
                    <h3>Last Customer Message</h3>
                    <div class="message-box">
                        "{alert_data['last_message']}"
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{alert_data['dashboard_link']}" class="cta-button">
                            🎯 View Conversation & Take Over
                        </a>
                    </div>
                    
                    <div style="background: #f9fafb; padding: 15px; border-radius: 6px; font-size: 14px;">
                        <p style="margin: 0;"><strong>What happens next?</strong></p>
                        <p style="margin: 10px 0 0 0;">The AI has automatically paused responses for this conversation. 
                        Click the button above to view the full chat history and take manual control.</p>
                    </div>
                </div>
                
                <div class="footer">
                    <p>This is an automated alert from AUREM AI Business Platform</p>
                    <p>Event ID: {alert_data['event_id']} | Conversation ID: {alert_data['conversation_id']}</p>
                    <p>&copy; 2026 {alert_data['business_name']}. Powered by AUREM.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        response = resend.Emails.send({
            "from": f"AUREM Alerts <alerts@aurem.ai>",
            "to": to_email,
            "subject": subject,
            "html": html_content
        })
        
        logger.info(f"[EmailNotification] 🚨 PANIC ALERT sent to {to_email}")
        return True
    
    except Exception as e:
        logger.error(f"[EmailNotification] Error sending panic alert: {e}")
        return False
