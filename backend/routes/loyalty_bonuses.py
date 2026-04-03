# ============================================================
# TASK 7: BIRTHDAY + REFERRAL BONUS TRIGGERS
# ============================================================

import os
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Database reference - will be set by server.py
db = None

def set_db(database):
    global db
    db = database


# ═══════════════════════════════════════════════════════════
# BIRTHDAY BONUS — Daily Scheduler
# ═══════════════════════════════════════════════════════════

async def check_birthday_bonuses() -> dict:
    """
    Runs daily at 9 AM EST.
    Awards 100 Roots to customers whose birthday is today.
    Prevents duplicate awards by tracking birthday_bonus_year.
    """
    from routes.whatsapp_templates import notify_birthday_bonus
    from routes.reroots_p0_fixes import sendgrid_send_email
    
    today = datetime.now(timezone.utc)
    current_year = today.year
    
    processed = 0
    errors = []
    
    # Find customers with birthday today (checking both 'dob' and 'birthday' fields)
    # Also check users collection
    collections_to_check = ['customers', 'users', 'loyalty_members']
    
    for collection_name in collections_to_check:
        try:
            collection = db[collection_name]
            
            # Build query for birthday match
            # Support different date formats: dob, birthday, date_of_birth
            pipeline = [
                {
                    '$addFields': {
                        'birth_date': {
                            '$ifNull': ['$dob', {'$ifNull': ['$birthday', '$date_of_birth']}]
                        }
                    }
                },
                {
                    '$match': {
                        'birth_date': {'$exists': True, '$ne': None},
                        '$expr': {
                            '$and': [
                                {'$eq': [{'$month': '$birth_date'}, today.month]},
                                {'$eq': [{'$dayOfMonth': '$birth_date'}, today.day]}
                            ]
                        },
                        'birthday_bonus_year': {'$ne': current_year}
                    }
                }
            ]
            
            customers = await collection.aggregate(pipeline).to_list(length=500)
            
            for customer in customers:
                try:
                    customer_id = str(customer.get('_id', customer.get('id', '')))
                    customer_email = customer.get('email', '')
                    
                    if not customer_email:
                        continue
                    
                    # Award 100 Roots
                    bonus_points = 100
                    
                    # Update in loyalty_members collection (primary)
                    member = await db.loyalty_members.find_one({'email': customer_email})
                    if member:
                        await db.loyalty_members.update_one(
                            {'email': customer_email},
                            {
                                '$inc': {'points': bonus_points, 'lifetimeEarned': bonus_points},
                                '$set': {'birthday_bonus_year': current_year}
                            }
                        )
                        new_balance = member.get('points', 0) + bonus_points
                    else:
                        # Create new loyalty member
                        await db.loyalty_members.insert_one({
                            'email': customer_email,
                            'points': bonus_points,
                            'tier': 'Standard',
                            'totalOrders': 0,
                            'lifetimeEarned': bonus_points,
                            'birthday_bonus_year': current_year,
                            'joinedAt': datetime.now(timezone.utc)
                        })
                        new_balance = bonus_points
                    
                    # Also update the source collection
                    await collection.update_one(
                        {'_id': customer['_id']},
                        {'$set': {'birthday_bonus_year': current_year}}
                    )
                    
                    # Log transaction
                    await db.loyalty_transactions.insert_one({
                        'email': customer_email,
                        'customer_id': customer_id,
                        'type': 'bonus',
                        'points': bonus_points,
                        'reason': f'Birthday bonus {current_year}',
                        'createdAt': datetime.now(timezone.utc)
                    })
                    
                    # Create wa.me link for admin
                    customer_data = {
                        '_id': customer_id,
                        'email': customer_email,
                        'first_name': customer.get('first_name', customer.get('name', '').split()[0] if customer.get('name') else ''),
                        'last_name': customer.get('last_name', ''),
                        'phone': customer.get('phone')
                    }
                    await notify_birthday_bonus(db, customer_data, new_balance)
                    
                    # Send birthday email
                    await send_birthday_bonus_email(
                        customer_email=customer_email,
                        customer_name=customer.get('first_name', customer_email.split('@')[0]),
                        bonus_points=bonus_points,
                        new_balance=new_balance
                    )
                    
                    processed += 1
                    logger.info(f"Birthday bonus awarded to {customer_email}")
                    
                except Exception as e:
                    errors.append(f"{customer.get('email', 'unknown')}: {str(e)}")
                    logger.error(f"Birthday bonus error for {customer.get('email')}: {e}")
                    
        except Exception as e:
            logger.error(f"Error checking {collection_name} for birthdays: {e}")
    
    return {
        'processed': processed,
        'errors': errors,
        'date': today.isoformat()
    }


async def send_birthday_bonus_email(customer_email: str, customer_name: str, bonus_points: int, new_balance: int):
    """Send birthday bonus email notification using dark theme."""
    try:
        from routers.email_service import send_birthday_email
        first_name = customer_name.split()[0] if customer_name else "there"
        send_birthday_email(customer_email, first_name, bonus_points)
    except Exception as e:
        # Fallback to old method if new service fails
        logging.warning(f"New email service failed, using fallback: {e}")
        from routes.reroots_p0_fixes import sendgrid_send_email
        
        first_name = customer_name.split()[0] if customer_name else "there"
        value = new_balance * 0.05
        
        html = f"""
        <div style="font-family: Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px; background: #060608;">
          <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="font-size: 28px; letter-spacing: 0.3em; color: #C9A86E; font-weight: 300;">RE<span style="color: #8A6B38;">ROOTS</span></h1>
            <p style="font-size: 11px; letter-spacing: 0.2em; color: #5C5548; text-transform: uppercase;">Happy Birthday!</p>
          </div>
          <div style="background: #0d0d10; border: 1px solid rgba(201,168,110,0.2); border-radius: 12px; padding: 32px; text-align: center;">
            <h2 style="font-size: 24px; color: #F0EBE0; font-weight: 300; margin-bottom: 8px;">Happy Birthday, {first_name}!</h2>
            <p style="font-size: 14px; color: #A89880; line-height: 1.7; margin-bottom: 20px;">
              ReRoots is celebrating with you! We've added a special gift to your account.
            </p>
            
            <div style="background: #1a1408; border: 1px solid #C9A86E; border-radius: 10px; padding: 20px; margin-bottom: 24px;">
              <p style="font-size: 11px; letter-spacing: 0.15em; color: #8A6B38; text-transform: uppercase; margin-bottom: 8px;">Birthday Gift</p>
              <p style="font-size: 36px; color: #C9A86E; font-weight: 600; margin-bottom: 4px;">+{bonus_points} Roots</p>
              <p style="font-size: 14px; color: #A89880;">New balance: {new_balance} Roots (${value:.2f})</p>
            </div>
            
            <a href="https://reroots.ca/app" style="display: inline-block; background: #C9A86E; color: #060608; padding: 14px 32px; border-radius: 4px; text-decoration: none; font-family: sans-serif; font-size: 12px; font-weight: 600; letter-spacing: 0.1em;">TREAT YOURSELF TODAY</a>
          </div>
          <p style="text-align: center; font-size: 11px; color: #3a3530; margin-top: 24px;">
            reroots.ca · Canadian Biotech Skincare
          </p>
        </div>
        """
        
        await sendgrid_send_email(
            to=customer_email,
            subject=f"Happy Birthday {first_name}! +{bonus_points} Roots for you",
            html_body=html
        )


# ═══════════════════════════════════════════════════════════
# REFERRAL BONUS — On First Purchase
# ═══════════════════════════════════════════════════════════

async def on_referral_first_purchase(referrer_id: str, referred_email: str) -> dict:
    """
    Awards 500 Roots to referrer when their referred customer makes first purchase.
    Called from order placement flow.
    """
    from routes.whatsapp_templates import notify_referral_bonus
    
    bonus_points = 500
    
    # Find referrer
    referrer = await db.users.find_one({'id': referrer_id}, {'_id': 0})
    if not referrer:
        referrer = await db.users.find_one({'_id': referrer_id})
    if not referrer:
        referrer = await db.customers.find_one({'id': referrer_id}, {'_id': 0})
    
    if not referrer:
        logger.warning(f"Referrer not found: {referrer_id}")
        return {'success': False, 'error': 'Referrer not found'}
    
    referrer_email = referrer.get('email', '')
    
    # Award 500 Roots to referrer
    member = await db.loyalty_members.find_one({'email': referrer_email})
    if member:
        await db.loyalty_members.update_one(
            {'email': referrer_email},
            {'$inc': {'points': bonus_points, 'lifetimeEarned': bonus_points}}
        )
        new_balance = member.get('points', 0) + bonus_points
    else:
        await db.loyalty_members.insert_one({
            'email': referrer_email,
            'points': bonus_points,
            'tier': 'Standard',
            'totalOrders': 0,
            'lifetimeEarned': bonus_points,
            'joinedAt': datetime.now(timezone.utc)
        })
        new_balance = bonus_points
    
    # Log transaction
    await db.loyalty_transactions.insert_one({
        'email': referrer_email,
        'customer_id': referrer_id,
        'type': 'bonus',
        'points': bonus_points,
        'reason': f'Referral bonus — {referred_email} first purchase',
        'referredEmail': referred_email,
        'createdAt': datetime.now(timezone.utc)
    })
    
    # Create wa.me link for admin
    referrer_data = {
        '_id': referrer_id,
        'id': referrer_id,
        'email': referrer_email,
        'first_name': referrer.get('first_name', referrer_email.split('@')[0]),
        'last_name': referrer.get('last_name', ''),
        'phone': referrer.get('phone')
    }
    await notify_referral_bonus(db, referrer_data, new_balance)
    
    # Send referral bonus email
    await send_referral_bonus_email(
        customer_email=referrer_email,
        customer_name=referrer.get('first_name', referrer_email.split('@')[0]),
        bonus_points=bonus_points,
        new_balance=new_balance,
        referred_email=referred_email
    )
    
    logger.info(f"Referral bonus {bonus_points} awarded to {referrer_email} for referring {referred_email}")
    
    return {
        'success': True,
        'referrer_email': referrer_email,
        'bonus_points': bonus_points,
        'new_balance': new_balance
    }


async def send_referral_bonus_email(customer_email: str, customer_name: str, bonus_points: int, new_balance: int, referred_email: str):
    """Send referral bonus email notification."""
    from routes.reroots_p0_fixes import sendgrid_send_email
    
    value = new_balance * 0.05
    
    # Mask the referred email for privacy
    email_parts = referred_email.split('@')
    masked_email = email_parts[0][:2] + '***@' + email_parts[1] if len(email_parts) == 2 else referred_email[:5] + '***'
    
    html = f"""
    <div style="font-family: 'Cormorant Garamond', Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px; background: #FDF9F9;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="font-size: 28px; letter-spacing: 0.3em; color: #2D2A2E; font-weight: 300;">RE<span style="color: #F8A5B8;">ROOTS</span></h1>
        <p style="font-size: 11px; letter-spacing: 0.2em; color: #C4BAC0; text-transform: uppercase;">Referral Bonus</p>
      </div>
      <div style="background: #fff; border: 1px solid #F0E8E8; border-radius: 12px; padding: 32px; text-align: center;">
        <div style="font-size: 64px; margin-bottom: 16px;">🎉</div>
        <h2 style="font-size: 24px; color: #2D2A2E; font-weight: 300; margin-bottom: 8px;">Your referral made a purchase!</h2>
        <p style="font-size: 14px; color: #8A8490; line-height: 1.7; margin-bottom: 20px;">
          {masked_email} just placed their first order. Thank you for sharing ReRoots!
        </p>
        
        <div style="background: #FDF9F9; border: 1px solid #F8A5B8; border-radius: 10px; padding: 20px; margin-bottom: 24px;">
          <p style="font-size: 11px; letter-spacing: 0.15em; color: #C4BAC0; text-transform: uppercase; margin-bottom: 8px;">Your Reward</p>
          <p style="font-size: 36px; color: #F8A5B8; font-weight: 600; margin-bottom: 4px;">+{bonus_points} Roots</p>
          <p style="font-size: 14px; color: #8A8490;">New balance: {new_balance} Roots (${value:.2f})</p>
        </div>
        
        <a href="https://reroots.ca/account" style="display: inline-block; background: #F8A5B8; color: #fff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-family: Inter, sans-serif; font-size: 13px; font-weight: 600; letter-spacing: 0.05em;">View Your Roots →</a>
        
        <p style="font-size: 12px; color: #8A8490; margin-top: 20px;">
          Keep sharing and earn more! 💙
        </p>
      </div>
      <p style="text-align: center; font-size: 11px; color: #C4BAC0; margin-top: 24px;">
        REROOTS AESTHETICS INC. · TORONTO, CANADA
      </p>
    </div>
    """
    
    await sendgrid_send_email(
        to=customer_email,
        subject=f"🎉 Your referral made a purchase! +{bonus_points} Roots for you",
        html_body=html
    )


# ═══════════════════════════════════════════════════════════
# HELPER: Check if order is customer's first purchase
# ═══════════════════════════════════════════════════════════

async def check_first_order(customer_email: str) -> bool:
    """Check if this is the customer's first order."""
    order_count = await db.orders.count_documents({
        '$or': [
            {'customerEmail': customer_email},
            {'email': customer_email},
            {'user_email': customer_email}
        ]
    })
    return order_count == 1  # Exactly 1 means this is their first


async def get_referrer_id(customer_email: str) -> Optional[str]:
    """Get the referrer ID for a customer if they were referred."""
    # Check referrals collection
    referral = await db.referrals.find_one({
        'referred_email': customer_email
    }, {'_id': 0, 'referrer_id': 1, 'referrer_email': 1})
    
    if referral:
        return referral.get('referrer_id') or referral.get('referrer_email')
    
    # Check if customer has referrer field
    customer = await db.users.find_one({'email': customer_email}, {'_id': 0, 'referred_by': 1, 'referrer_id': 1})
    if customer:
        return customer.get('referred_by') or customer.get('referrer_id')
    
    return None
