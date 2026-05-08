"""
PDF Report Generator for Customer Scans
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime

def generate_pdf_report(scan_result: dict) -> BytesIO:
    """Generate PDF report from scan results"""
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Container for PDF elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#D4AF37'),
        spaceAfter=12,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#D4AF37'),
        spaceAfter=10,
        spaceBefore=20
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#666666'),
        spaceAfter=8
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 10
    normal_style.leading = 14
    
    # Title
    elements.append(Paragraph("AUREM System Analysis Report", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Website Info
    elements.append(Paragraph(f"Website: {scan_result['website_url']}", normal_style))
    elements.append(Paragraph(f"Scan Date: {datetime.fromisoformat(scan_result['scan_date']).strftime('%B %d, %Y at %I:%M %p')}", normal_style))
    elements.append(Paragraph(f"Scan ID: {scan_result['scan_id']}", normal_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Executive Summary
    elements.append(Paragraph("Executive Summary", heading_style))
    
    summary_data = [
        ['Metric', 'Current State', 'Status'],
        ['Overall Score', f"{scan_result['overall_score']}/100", get_status(scan_result['overall_score'])],
        ['Total Issues Found', str(scan_result['issues_found']), ''],
        ['Critical Issues', str(scan_result['critical_issues']), 'Needs Immediate Action' if scan_result['critical_issues'] > 0 else 'Good'],
        ['Performance Score', f"{scan_result['performance']['score']}/100", get_status(scan_result['performance']['score'])],
        ['Security Score', f"{scan_result['security']['score']}/100", get_status(scan_result['security']['score'])],
        ['SEO Score', f"{scan_result['seo']['score']}/100", get_status(scan_result['seo']['score'])],
        ['Accessibility Score', f"{scan_result['accessibility']['score']}/100", get_status(scan_result['accessibility']['score'])],
    ]
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 1.5*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D4AF37')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # AUREM Impact Section
    elements.append(Paragraph("Expected Impact with AUREM", heading_style))
    impact = scan_result['aurem_impact']
    
    impact_data = [
        ['Improvement Area', 'Expected Gain'],
        ['Speed Improvement', f"+{impact['speed_improvement_percent']}%"],
        ['Security Score Improvement', f"+{impact['security_score_improvement']} points"],
        ['SEO Ranking Boost', f"+{impact['seo_ranking_boost']}%"],
        ['Time Saved Monthly', impact['estimated_time_saved_monthly']],
        ['Cost Savings Monthly', impact['estimated_cost_savings_monthly']],
        ['Automation Coverage', impact['automation_coverage']],
        ['ROI Timeline', impact['roi_timeline']],
    ]
    
    impact_table = Table(impact_data, colWidths=[3*inch, 3*inch])
    impact_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#E8F5E9')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#4CAF50')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    
    elements.append(impact_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Before vs After Comparison
    elements.append(Paragraph("Before vs After AUREM", heading_style))
    
    before_after_data = [
        ['Metric', 'Before AUREM', 'After AUREM', 'Improvement'],
        [
            'Critical Issues',
            str(impact['before_aurem']['critical_issues']),
            str(impact['after_aurem']['critical_issues']),
            f"-{impact['before_aurem']['critical_issues']} issues"
        ],
        [
            'Warnings',
            str(impact['before_aurem']['warnings']),
            str(impact['after_aurem']['warnings']),
            f"-{impact['before_aurem']['warnings'] - impact['after_aurem']['warnings']} warnings"
        ],
        [
            'Manual Work (weekly)',
            f"{impact['before_aurem']['manual_work_hours_weekly']}h",
            f"{impact['after_aurem']['manual_work_hours_weekly']}h",
            f"-{impact['before_aurem']['manual_work_hours_weekly'] - impact['after_aurem']['manual_work_hours_weekly']}h/week"
        ],
    ]
    
    before_after_table = Table(before_after_data, colWidths=[1.8*inch, 1.5*inch, 1.5*inch, 1.7*inch])
    before_after_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D4AF37')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    
    elements.append(before_after_table)
    elements.append(PageBreak())
    
    # Detailed Findings
    elements.append(Paragraph("Detailed Findings", heading_style))
    
    # Top Recommendations
    if scan_result.get('recommendations'):
        elements.append(Paragraph("Top Priority Recommendations", subheading_style))
        
        for i, rec in enumerate(scan_result['recommendations'][:10], 1):
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(f"{i}. {rec['title']} ({rec['category'].upper()})", 
                                    ParagraphStyle('RecTitle', parent=normal_style, fontName='Helvetica-Bold')))
            elements.append(Paragraph(f"Priority: {rec['priority'].upper()}", normal_style))
            elements.append(Paragraph(f"Issue: {rec['description']}", normal_style))
            elements.append(Paragraph(f"<b>AUREM Solution:</b> {rec['solution']}", 
                                    ParagraphStyle('Solution', parent=normal_style, textColor=colors.HexColor('#4CAF50'))))
            elements.append(Spacer(1, 0.1*inch))
    
    # Footer
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph("_______________________________________________________________________________", 
                             ParagraphStyle('Line', parent=normal_style, textColor=colors.HexColor('#CCCCCC'))))
    elements.append(Spacer(1, 0.1*inch))
    footer_text = f"Generated by AUREM System Scanner | Report ID: {scan_result['scan_id']} | © AUREM AI Platform"
    elements.append(Paragraph(footer_text, 
                             ParagraphStyle('Footer', parent=normal_style, fontSize=8, textColor=colors.HexColor('#999999'), alignment=TA_CENTER)))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

def get_status(score):
    """Get status text based on score"""
    if score >= 80:
        return "Excellent"
    elif score >= 60:
        return "Good"
    elif score >= 40:
        return "Needs Improvement"
    else:
        return "Critical"
