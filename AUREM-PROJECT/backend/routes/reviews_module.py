"""
Task 4: Reviews Module + Day 21 Trigger
- Review request creation and management
- Review submission and reward handling
- Day 21 automated review request trigger
- Admin review moderation endpoints
"""

import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Google Review Link from environment
GOOGLE_REVIEW_LINK = os.environ.get('GOOGLE_REVIEW_LINK', 'https://g.page/r/CY76Se2EyM-_EBM/review')


async def check_day21_review_requests(db):
    """
    Runs daily. Finds customers who placed an order 21 days ago
    and haven't received a review request yet.
    """
    now = datetime.now(timezone.utc)
    target_date_start = now - timedelta(days=21)
    target_date_end = target_date_start + timedelta(hours=24)
    
    logger.info(f"Checking for Day 21 review requests (orders from {target_date_start.date()})")
    
    # Find orders placed exactly 21 days ago
    orders = await db.orders.find({
        'created_at': {
            '$gte': target_date_start.isoformat(),
            '$lt': target_date_end.isoformat()
        },
        'status': {'$in': ['delivered', 'completed', 'processing', 'shipped']}
    }).to_list(length=100)
    
    requests_created = 0
    
    for order in orders:
        order_id = str(order.get('_id', order.get('id', '')))
        customer_email = order.get('customerEmail') or order.get('email')
        user_id = order.get('user_id')
        
        if not customer_email:
            continue
        
        # Check if review request already sent for this order
        existing = await db.review_requests.find_one({
            'order_id': order_id,
            'email': customer_email
        })
        if existing:
            continue
        
        # Get customer info
        customer = None
        if user_id:
            customer = await db.users.find_one({'id': user_id}, {'_id': 0})
        if not customer:
            customer = await db.users.find_one({'email': customer_email}, {'_id': 0})
        
        customer_name = order.get('customerName') or (f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() if customer else customer_email.split('@')[0])
        customer_phone = customer.get('phone') if customer else None
        
        # Generate secure token
        token = str(uuid.uuid4())
        
        # Create review request record
        await db.review_requests.insert_one({
            'customer_id': user_id or customer_email,
            'order_id': order_id,
            'email': customer_email,
            'phone': customer_phone,
            'customer_name': customer_name,
            'token': token,
            'status': 'pending',
            'created_at': now,
            'expires_at': now + timedelta(days=30),
            'submitted_at': None
        })
        
        # Send email + WhatsApp notifications
        try:
            await send_day21_review_request(
                db=db,
                customer_email=customer_email,
                customer_name=customer_name,
                customer_phone=customer_phone,
                token=token
            )
            requests_created += 1
        except Exception as e:
            logger.warning(f"Failed to send Day 21 review request to {customer_email}: {e}")
    
    logger.info(f"Day 21 review requests: {requests_created} created from {len(orders)} orders")
    return requests_created


async def send_day21_review_request(db, customer_email: str, customer_name: str, customer_phone: Optional[str], token: str):
    """Send Day 21 review request via email and WhatsApp."""
    from routes.reroots_p0_fixes import sendgrid_send_email
    from services.twilio_service import send_whatsapp_message
    
    first_name = customer_name.split()[0] if customer_name else "there"
    review_url = f"https://reroots.ca/review/{token}"
    
    # Email
    email_html = f"""
    <div style="font-family: 'Cormorant Garamond', Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px; background: #FDF9F9;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="font-size: 28px; letter-spacing: 0.3em; color: #2D2A2E; font-weight: 300;">RE<span style="color: #F8A5B8;">ROOTS</span></h1>
        <p style="font-size: 11px; letter-spacing: 0.2em; color: #C4BAC0; text-transform: uppercase;">21-Day Check-In</p>
      </div>
      <div style="background: #fff; border: 1px solid #F0E8E8; border-radius: 12px; padding: 32px;">
        <h2 style="font-size: 22px; color: #2D2A2E; font-weight: 300; margin-bottom: 16px;">How is your skin doing, {first_name}?</h2>
        <p style="font-size: 14px; color: #8A8490; line-height: 1.8; margin-bottom: 20px;">
          It's been 3 weeks since your AURA-GEN serum arrived.
        </p>
        <p style="font-size: 14px; color: #8A8490; line-height: 1.8; margin-bottom: 20px;">
          By now you should be seeing early results — improved texture, more even tone, that first glow of PDRN doing its work.
        </p>
        <p style="font-size: 14px; color: #2D2A2E; line-height: 1.8; margin-bottom: 24px; font-weight: 500;">
          We'd love to hear how your skin is responding.
        </p>
        
        <div style="background: #FDF9F9; border: 1px solid #F8A5B8; border-radius: 10px; padding: 20px; margin-bottom: 24px; text-align: center;">
          <p style="font-size: 11px; letter-spacing: 0.15em; color: #C4BAC0; text-transform: uppercase; margin-bottom: 8px;">Share Your Experience</p>
          <p style="font-size: 24px; color: #F8A5B8; font-weight: 600; margin-bottom: 4px;">Earn 100 Roots</p>
          <p style="font-size: 14px; color: #8A8490;">That's $5.00 toward your next order!</p>
        </div>
        
        <a href="{review_url}" style="display: block; background: #F8A5B8; color: #fff; text-align: center; padding: 16px; border-radius: 8px; text-decoration: none; font-family: Inter, sans-serif; font-size: 14px; font-weight: 600; letter-spacing: 0.05em; margin-bottom: 20px;">Leave Your Review → Earn 100 Roots</a>
        
        <div style="border-top: 1px solid #F0E8E8; padding-top: 20px; margin-top: 20px;">
          <p style="font-size: 13px; color: #8A8490; text-align: center; margin-bottom: 12px;">
            Loving it? Help other Canadians discover PDRN skincare:
          </p>
          <a href="{GOOGLE_REVIEW_LINK}" style="display: block; background: #fff; color: #2D2A2E; text-align: center; padding: 12px; border-radius: 8px; border: 1px solid #2D2A2E; text-decoration: none; font-family: Inter, sans-serif; font-size: 13px; font-weight: 500;">Leave a Google Review →</a>
        </div>
      </div>
      <p style="text-align: center; font-size: 11px; color: #C4BAC0; margin-top: 24px;">
        Thank you for choosing ReRoots 🌿<br>
        - Tj & the team<br><br>
        REROOTS AESTHETICS INC. · TORONTO, CANADA
      </p>
    </div>
    """
    
    await sendgrid_send_email(
        to=customer_email,
        subject="How is your skin doing? 🌿 Share your experience",
        html_body=email_html
    )
    
    # WhatsApp (if phone available)
    if customer_phone:
        whatsapp_msg = f"""Hi {first_name}! 🌿

It's been 3 weeks with your AURA-GEN serum — how's your skin feeling?

We'd love your honest feedback, and we'll reward you with *100 Roots* ($5.00 value) for sharing it 🙏

Leave your review here:
{review_url}

And if you're loving the results, a Google review means the world to a small Canadian brand like ours 💙
{GOOGLE_REVIEW_LINK}"""
        
        await send_whatsapp_message(customer_phone, whatsapp_msg)
    
    logger.info(f"Day 21 review request sent to {customer_email}")


async def get_review_request_by_token(db, token: str) -> Optional[dict]:
    """Get and validate a review request by token."""
    request_record = await db.review_requests.find_one({
        'token': token,
        'status': 'pending'
    }, {'_id': 0})
    
    if not request_record:
        return None
    
    # Check expiry
    expires_at = request_record.get('expires_at')
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        # Make expires_at timezone-aware if it's naive
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            await db.review_requests.update_one(
                {'token': token},
                {'$set': {'status': 'expired'}}
            )
            return None
    
    return request_record


async def submit_review(db, token: str, rating: int, headline: str, body: str) -> dict:
    """
    Submit a review and award 100 Roots.
    Returns success status and new balance.
    """
    # Validate token
    request_record = await get_review_request_by_token(db, token)
    
    if not request_record:
        return {'success': False, 'error': 'Invalid or expired review link'}
    
    # Validate input
    if rating < 1 or rating > 5:
        return {'success': False, 'error': 'Rating must be between 1 and 5'}
    
    if len(body.strip()) < 20:
        return {'success': False, 'error': 'Please write at least 20 characters'}
    
    customer_email = request_record.get('email')
    customer_id = request_record.get('customer_id')
    order_id = request_record.get('order_id')
    customer_name = request_record.get('customer_name', '')
    customer_phone = request_record.get('phone')
    now = datetime.now(timezone.utc)
    
    # Save review
    await db.reviews.insert_one({
        'customer_id': customer_id,
        'customer_email': customer_email,
        'order_id': order_id,
        'token': token,
        'rating': rating,
        'headline': headline.strip(),
        'body': body.strip(),
        'product_name': 'AURA-GEN PDRN+TXA Serum',
        'status': 'pending',  # admin approves before showing on site
        'roots_awarded': True,
        'created_at': now,
        'approved_at': None
    })
    
    # Mark request as submitted
    await db.review_requests.update_one(
        {'token': token},
        {'$set': {
            'status': 'submitted',
            'submitted_at': now
        }}
    )
    
    # Award 100 Roots - check both collections
    points_to_award = 100
    
    # Try loyalty_members first (new system)
    member = await db.loyalty_members.find_one({'email': customer_email})
    if member:
        await db.loyalty_members.update_one(
            {'email': customer_email},
            {'$inc': {'points': points_to_award, 'lifetimeEarned': points_to_award}}
        )
    else:
        # Create new loyalty member record
        await db.loyalty_members.insert_one({
            'email': customer_email,
            'points': points_to_award,
            'tier': 'Standard',
            'totalOrders': 0,
            'lifetimeEarned': points_to_award,
            'joinedAt': now
        })
    
    # Log transaction
    await db.loyalty_transactions.insert_one({
        'email': customer_email,
        'type': 'bonus',
        'points': points_to_award,
        'reason': 'Review submitted — thank you!',
        'orderId': order_id,
        'createdAt': now
    })
    
    # Get updated balance
    updated_member = await db.loyalty_members.find_one({'email': customer_email}, {'_id': 0, 'points': 1})
    new_balance = updated_member.get('points', points_to_award) if updated_member else points_to_award
    
    # Send thank you notifications
    try:
        await send_review_thankyou(
            db=db,
            customer_email=customer_email,
            customer_name=customer_name,
            customer_phone=customer_phone,
            new_balance=new_balance
        )
    except Exception as e:
        logger.warning(f"Review thank you notification failed: {e}")
    
    logger.info(f"Review submitted by {customer_email} - awarded {points_to_award} Roots")
    
    return {
        'success': True,
        'roots_awarded': points_to_award,
        'new_balance': new_balance,
        'google_review_link': GOOGLE_REVIEW_LINK
    }


async def send_review_thankyou(db, customer_email: str, customer_name: str, customer_phone: Optional[str], new_balance: int):
    """Send thank you notification after review submission."""
    from routes.reroots_p0_fixes import sendgrid_send_email
    from services.twilio_service import send_whatsapp_message
    
    first_name = customer_name.split()[0] if customer_name else "there"
    value = new_balance * 0.05
    
    # Email
    email_html = f"""
    <div style="font-family: 'Cormorant Garamond', Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px; background: #FDF9F9;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="font-size: 28px; letter-spacing: 0.3em; color: #2D2A2E; font-weight: 300;">RE<span style="color: #F8A5B8;">ROOTS</span></h1>
        <p style="font-size: 11px; letter-spacing: 0.2em; color: #C4BAC0; text-transform: uppercase;">Thank You!</p>
      </div>
      <div style="background: #fff; border: 1px solid #F0E8E8; border-radius: 12px; padding: 32px; text-align: center;">
        <div style="font-size: 48px; margin-bottom: 16px;">✅</div>
        <h2 style="font-size: 22px; color: #2D2A2E; font-weight: 300; margin-bottom: 8px;">Thank you, {first_name}!</h2>
        <p style="font-size: 14px; color: #8A8490; line-height: 1.7; margin-bottom: 20px;">
          Your review has been received and is pending approval.
        </p>
        
        <div style="background: #FDF9F9; border: 1px solid #F8A5B8; border-radius: 10px; padding: 20px; margin-bottom: 24px;">
          <p style="font-size: 11px; letter-spacing: 0.15em; color: #C4BAC0; text-transform: uppercase; margin-bottom: 8px;">Roots Awarded</p>
          <p style="font-size: 32px; color: #F8A5B8; font-weight: 600; margin-bottom: 4px;">+100 Roots</p>
          <p style="font-size: 14px; color: #8A8490;">New balance: {new_balance} Roots (${value:.2f})</p>
        </div>
        
        <div style="border-top: 1px solid #F0E8E8; padding-top: 20px; margin-top: 20px;">
          <p style="font-size: 13px; color: #2D2A2E; font-weight: 500; margin-bottom: 12px;">
            Love ReRoots? Help other Canadians discover PDRN skincare 💙
          </p>
          <a href="{GOOGLE_REVIEW_LINK}" style="display: block; background: #2D2A2E; color: #fff; text-align: center; padding: 14px; border-radius: 8px; text-decoration: none; font-family: Inter, sans-serif; font-size: 13px; font-weight: 600; margin-bottom: 12px;">Leave a Google Review →</a>
          <p style="font-size: 12px; color: #8A8490;">
            Takes 30 seconds and means everything to a small Canadian brand like ours.
          </p>
        </div>
      </div>
      <p style="text-align: center; font-size: 11px; color: #C4BAC0; margin-top: 24px;">
        REROOTS AESTHETICS INC. · TORONTO, CANADA
      </p>
    </div>
    """
    
    await sendgrid_send_email(
        to=customer_email,
        subject="Thank you for your review! 🌿 +100 Roots added",
        html_body=email_html
    )
    
    # WhatsApp
    if customer_phone:
        whatsapp_msg = f"""✅ Review received, {first_name}! Thank you 🙏

*+100 Roots* have been added to your account
New balance: *{new_balance} Roots* (${value:.2f})

────────────────────
One more ask — if you're loving ReRoots,
a Google review helps other Canadians
discover PDRN skincare 💙

{GOOGLE_REVIEW_LINK}

Takes 30 seconds and means everything
to our small Canadian team 🌿"""
        
        await send_whatsapp_message(customer_phone, whatsapp_msg)
    
    # Task 6: Also create wa.me CRM action for admin panel
    try:
        from routes.whatsapp_templates import notify_review_thankyou
        customer_data = {
            'email': customer_email,
            'first_name': first_name,
            'last_name': ' '.join(customer_name.split()[1:]) if customer_name and len(customer_name.split()) > 1 else '',
            'phone': customer_phone
        }
        await notify_review_thankyou(db, customer_data, new_balance)
    except Exception as wa_err:
        logger.debug(f"wa.me review thank you action skipped: {wa_err}")


async def get_admin_reviews(db, status: str = 'pending', skip: int = 0, limit: int = 50) -> dict:
    """Get reviews for admin panel with optional status filter."""
    query = {}
    if status != 'all':
        query['status'] = status
    
    reviews = await db.reviews.find(
        query,
        {'_id': 0}
    ).sort('created_at', -1).skip(skip).limit(limit).to_list(limit)
    
    total = await db.reviews.count_documents(query)
    
    # Get stats
    pending_count = await db.reviews.count_documents({'status': 'pending'})
    approved_count = await db.reviews.count_documents({'status': 'approved'})
    rejected_count = await db.reviews.count_documents({'status': 'rejected'})
    
    return {
        'reviews': reviews,
        'total': total,
        'stats': {
            'pending': pending_count,
            'approved': approved_count,
            'rejected': rejected_count
        }
    }


async def approve_review(db, token: str) -> dict:
    """Approve a review for display on site."""
    result = await db.reviews.update_one(
        {'token': token},
        {'$set': {
            'status': 'approved',
            'approved_at': datetime.now(timezone.utc)
        }}
    )
    return {'success': result.modified_count > 0}


async def reject_review(db, token: str) -> dict:
    """Reject a review."""
    result = await db.reviews.update_one(
        {'token': token},
        {'$set': {'status': 'rejected'}}
    )
    return {'success': result.modified_count > 0}
