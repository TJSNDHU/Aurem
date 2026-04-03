"""
Central Orchestrator - The Brain of ReRoots Autonomous Systems
═══════════════════════════════════════════════════════════════════
Unifies all 6 autonomous systems into one intelligent loop:
- Auto-Heal (crash recovery)
- Auto-Repair (code bug fixes)
- Diagnostic AI (error explanation)
- Automation Intelligence (suggestion evaluation)
- Compliance Monitor (content blocking)
- Site Audit (daily feature testing)

ONE brain. ONE loop. ONE WhatsApp message.
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import logging
import asyncio
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

# Database reference - set during startup
_db = None

def set_db(db):
    global _db
    _db = db


# ══════════════════════════════════════════════════════════════════
# EVENT TYPES
# ══════════════════════════════════════════════════════════════════

EVENT_TYPES = {
    'crash': 'System crash or service down',
    'bug': 'Code error or exception',
    'suggestion': 'Improvement suggestion from any source',
    'violation': 'Business rule or compliance violation',
    'performance': 'Slow response or degraded service',
    'security': 'Suspicious activity or rate limit breach',
    'business': 'Stock low, revenue alert, CNF reminder',
}

# Deduplication store - prevents 4 alerts about same issue
recent_events: Dict[str, datetime] = {}

# Deduplication window in seconds (30 minutes)
DEDUP_WINDOW_SECONDS = 1800


class Orchestrator:
    """
    Central brain that receives ALL system events and routes them intelligently.
    Replaces scattered WhatsApp calls with unified, deduplicated notifications.
    """
    
    async def receive(
        self, 
        event_type: str, 
        data: dict, 
        source: str
    ) -> dict:
        """
        Single entry point for ALL system events.
        Every service calls this instead of sending WhatsApp directly.
        
        Args:
            event_type: One of EVENT_TYPES keys
            data: Event-specific data dict
            source: Which service sent this (auto_heal, auto_repair, etc.)
        
        Returns:
            dict with action taken and status
        """
        if _db is None:
            logger.warning("[Orchestrator] Database not initialized")
            return {'status': 'error', 'message': 'Database not ready'}
        
        # Create deduplication key from event type and key data
        event_key = f"{event_type}:{data.get('key', str(data)[:50])}"
        now = datetime.now(timezone.utc)
        
        # Deduplicate - same event within 30 min = ignore
        if event_key in recent_events:
            last_seen = recent_events[event_key]
            time_diff = (now - last_seen).total_seconds()
            if time_diff < DEDUP_WINDOW_SECONDS:
                logger.debug(f"[Orchestrator] Deduplicated event: {event_key}")
                return {'status': 'deduplicated', 'key': event_key}
        
        recent_events[event_key] = now
        
        # Log event to database
        event_id = f"{source}_{int(now.timestamp() * 1000)}"
        event_doc = {
            'event_id': event_id,
            'type': event_type,
            'data': data,
            'source': source,
            'status': 'received',
            'timestamp': now.isoformat(),
            'created_at': now
        }
        
        try:
            await _db.orchestrator_events.insert_one(event_doc)
        except Exception as e:
            logger.error(f"[Orchestrator] Failed to log event: {e}")
        
        # Route to appropriate handler
        result = await self.route(event_type, data, event_id)
        
        # Update event record with result
        try:
            await _db.orchestrator_events.update_one(
                {'event_id': event_id},
                {'$set': {
                    'status': result.get('action', 'unknown'),
                    'result': result,
                    'completed_at': datetime.now(timezone.utc).isoformat()
                }}
            )
        except Exception as e:
            logger.error(f"[Orchestrator] Failed to update event: {e}")
        
        logger.info(f"[Orchestrator] {event_type} from {source} → {result.get('action')}")
        return result
    
    async def route(self, event_type: str, data: dict, event_id: str) -> dict:
        """Routes event to correct autonomous handler."""
        
        handlers = {
            'crash': self.handle_crash,
            'bug': self.handle_bug,
            'suggestion': self.handle_suggestion,
            'violation': self.handle_violation,
            'security': self.handle_security,
            'business': self.handle_business,
            'performance': self.handle_performance,
        }
        
        handler = handlers.get(event_type, self.handle_unknown)
        return await handler(data, event_id)
    
    async def handle_crash(self, data: dict, event_id: str) -> dict:
        """Crash = auto-restart first, diagnose second."""
        service = data.get('service', 'backend')
        error = data.get('error', 'Unknown error')
        
        # Try to restart service
        try:
            result = subprocess.run(
                ['sudo', 'supervisorctl', 'restart', service],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                logger.warning(f"[Orchestrator] Restart returned non-zero: {result.stderr}")
        except Exception as e:
            logger.error(f"[Orchestrator] Restart failed: {e}")
        
        # Wait for service to come up
        await asyncio.sleep(5)
        
        # Test if restart worked
        recovered = False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                health_url = os.environ.get('FRONTEND_URL', 'https://reroots.ca')
                r = await client.get(f"{health_url}/api/health")
                recovered = r.status_code == 200
        except Exception:
            recovered = False
        
        # Notify - urgent if still down
        emoji = '✅' if recovered else '🚨'
        status_text = 'auto-recovered' if recovered else 'STILL DOWN - MANUAL ACTION NEEDED'
        
        await self.notify(
            f"{emoji} Crash detected + {status_text}",
            f"Service: {service}\nError: {error[:150]}",
            urgent=not recovered
        )
        
        return {
            'action': 'restarted',
            'recovered': recovered,
            'service': service
        }
    
    async def handle_bug(self, data: dict, event_id: str) -> dict:
        """Bug = check known fixes, apply if safe, ask if not."""
        error_text = data.get('error', '')
        
        # Try to apply known fix from auto_repair
        try:
            from services.auto_repair import KNOWN_FIXES
            
            for fix_name, fix_data in KNOWN_FIXES.items():
                pattern = fix_data.get('pattern', '').lower()
                if pattern and pattern in error_text.lower():
                    # Found a known fix
                    await self.notify(
                        '🔧 Bug detected - known fix available',
                        f"Error: {error_text[:100]}\nFix: {fix_data.get('description', fix_name)}"
                    )
                    return {
                        'action': 'known_fix_available',
                        'fix': fix_name,
                        'description': fix_data.get('description')
                    }
        except ImportError:
            pass
        
        # Unknown bug - queue for approval
        await self.request_approval(
            event_id=event_id,
            title='Unknown bug detected',
            description=error_text[:150],
            suggested_fix='Manual investigation required',
            risk='medium'
        )
        
        return {'action': 'pending_approval', 'event_id': event_id}
    
    async def handle_suggestion(self, data: dict, event_id: str) -> dict:
        """Suggestion = classify by risk, auto-apply if safe."""
        suggestion = data.get('suggestion', '')
        source = data.get('source', 'system')
        risk = data.get('risk', 'low')
        
        # Low risk suggestions get queued for daily digest
        if risk == 'low':
            await _db.notification_queue.insert_one({
                'title': f'💡 Suggestion from {source}',
                'body': suggestion[:200],
                'urgent': False,
                'sent': False,
                'created_at': datetime.now(timezone.utc)
            })
            return {'action': 'queued_for_digest'}
        
        # Medium/high risk suggestions need approval
        await self.request_approval(
            event_id=event_id,
            title=f'Suggestion from {source}',
            description=suggestion[:150],
            suggested_fix='Review and implement manually',
            risk=risk
        )
        
        return {'action': 'pending_approval'}
    
    async def handle_violation(self, data: dict, event_id: str) -> dict:
        """Violation = always block, always notify."""
        rule = data.get('rule', 'unknown')
        content = data.get('content', '')
        
        await self.notify(
            '🚫 BLOCKED: Rule violation',
            f"Rule: {rule}\nContent: {content[:100]}",
            urgent=True
        )
        
        return {'action': 'blocked', 'rule': rule}
    
    async def handle_security(self, data: dict, event_id: str) -> dict:
        """Security event = log, alert if severe."""
        ip = data.get('ip', 'unknown')
        event_name = data.get('event', '')
        severity = data.get('severity', 'low')
        
        # Log to security collection
        await _db.security_log.insert_one({
            'ip': ip,
            'event': event_name,
            'severity': severity,
            'event_id': event_id,
            'timestamp': datetime.now(timezone.utc)
        })
        
        if severity in ['high', 'critical']:
            await self.notify(
                '🔒 Security alert',
                f"Event: {event_name}\nIP: {ip}\nSeverity: {severity.upper()}",
                urgent=True
            )
        
        return {'action': 'logged', 'severity': severity}
    
    async def handle_business(self, data: dict, event_id: str) -> dict:
        """Business events = stock, revenue, CNF reminders."""
        title = data.get('title', 'Business alert')
        message = data.get('message', '')
        urgent = data.get('urgent', False)
        
        if urgent:
            await self.notify(f"📊 {title}", message, urgent=True)
        else:
            await _db.notification_queue.insert_one({
                'title': f'📊 {title}',
                'body': message,
                'urgent': False,
                'sent': False,
                'created_at': datetime.now(timezone.utc)
            })
        
        return {'action': 'notified' if urgent else 'queued_for_digest'}
    
    async def handle_performance(self, data: dict, event_id: str) -> dict:
        """Performance = log, alert if severely degraded."""
        endpoint = data.get('endpoint', '')
        response_time = data.get('response_time_ms', 0)
        threshold = data.get('threshold_ms', 5000)
        
        if response_time > threshold * 2:  # More than 2x threshold
            await self.notify(
                '🐢 Severe performance degradation',
                f"Endpoint: {endpoint}\nResponse time: {response_time}ms (threshold: {threshold}ms)",
                urgent=True
            )
            return {'action': 'alerted', 'response_time': response_time}
        
        # Queue for digest
        await _db.notification_queue.insert_one({
            'title': '🐢 Slow endpoint detected',
            'body': f"{endpoint}: {response_time}ms",
            'urgent': False,
            'sent': False,
            'created_at': datetime.now(timezone.utc)
        })
        
        return {'action': 'queued_for_digest'}
    
    async def handle_unknown(self, data: dict, event_id: str) -> dict:
        """Unknown events = log and queue for review."""
        await _db.notification_queue.insert_one({
            'title': 'ℹ️ Unknown system event',
            'body': str(data)[:200],
            'urgent': False,
            'sent': False,
            'created_at': datetime.now(timezone.utc)
        })
        
        return {'action': 'queued_for_review'}
    
    async def request_approval(
        self,
        event_id: str,
        title: str,
        description: str,
        suggested_fix: str,
        risk: str
    ):
        """Sends WhatsApp approval request to admin."""
        approval_doc = {
            'id': event_id,
            'event_id': event_id,
            'title': title,
            'description': description,
            'suggested_fix': suggested_fix,
            'risk': risk,
            'status': 'pending',
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        await _db.pending_approvals.insert_one(approval_doc)
        
        # Send WhatsApp approval request
        tj_number = os.environ.get('TJ_WHATSAPP_NUMBER')
        if tj_number:
            try:
                from services.twilio_service import send_whatsapp_message
                await send_whatsapp_message(
                    tj_number,
                    f"""🤖 Needs your approval:

{title}
Issue: {description}
Suggested: {suggested_fix[:150]}
Risk: {risk.upper()}

Reply:
APPROVE {event_id[:8]}
REJECT {event_id[:8]}"""
                )
            except Exception as e:
                logger.error(f"[Orchestrator] WhatsApp approval request failed: {e}")
    
    async def notify(self, title: str, body: str, urgent: bool = False):
        """
        Smart notification - batches non-urgent alerts.
        Only sends immediately if urgent.
        """
        if urgent:
            tj_number = os.environ.get('TJ_WHATSAPP_NUMBER')
            if tj_number:
                try:
                    from services.twilio_service import send_whatsapp_message
                    await send_whatsapp_message(tj_number, f"{title}\n\n{body}")
                except Exception as e:
                    logger.error(f"[Orchestrator] Urgent notification failed: {e}")
        else:
            # Queue for daily digest
            await _db.notification_queue.insert_one({
                'title': title,
                'body': body,
                'urgent': False,
                'sent': False,
                'created_at': datetime.now(timezone.utc)
            })


# ══════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ══════════════════════════════════════════════════════════════════

orchestrator = Orchestrator()


# ══════════════════════════════════════════════════════════════════
# DAILY DIGEST
# ══════════════════════════════════════════════════════════════════

async def send_daily_digest():
    """
    Every morning 8am - sends ONE summary of everything
    that happened overnight instead of 20 separate alerts.
    """
    if _db is None:
        logger.warning("[Orchestrator] Cannot send digest - DB not ready")
        return
    
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    
    # Get events from last 24 hours
    events = await _db.orchestrator_events.find(
        {'created_at': {'$gte': since}},
        {'_id': 0}
    ).to_list(None)
    
    # Get queued notifications
    queued = await _db.notification_queue.find(
        {'sent': False},
        {'_id': 0}
    ).to_list(None)
    
    if not events and not queued:
        logger.info("[Orchestrator] Daily digest: nothing to report")
        return
    
    # Count by status
    auto_fixed = len([e for e in events if e.get('status') in ['auto_fixed', 'restarted']])
    blocked = len([e for e in events if e.get('status') == 'blocked'])
    pending = len([e for e in events if e.get('status') == 'pending_approval'])
    crashes = len([e for e in events if e.get('type') == 'crash'])
    recovered = len([e for e in events if e.get('result', {}).get('recovered') is True])
    
    # Build notification summary
    notif_summary = '\n'.join([f"• {n.get('title', 'Alert')}" for n in queued[:5]])
    if len(queued) > 5:
        notif_summary += f"\n• ... and {len(queued) - 5} more"
    
    # Determine health status
    health_status = '✅ Healthy'
    if pending > 0:
        health_status = '⏳ Pending approvals'
    if crashes > recovered:
        health_status = '⚠️ Active issues'
    
    summary = f"""☀️ Daily System Report — {datetime.now(timezone.utc).strftime('%b %d')}

✅ Auto-handled: {auto_fixed} issues
🚫 Blocked: {blocked} violations
⏳ Pending approval: {pending}
🔄 Crashes recovered: {recovered}/{crashes}

{f"Notifications:{chr(10)}{notif_summary}" if queued else "No queued notifications"}

System health: {health_status}"""
    
    # Send via WhatsApp
    tj_number = os.environ.get('TJ_WHATSAPP_NUMBER')
    if tj_number:
        try:
            from services.twilio_service import send_whatsapp_message
            await send_whatsapp_message(tj_number, summary)
            logger.info("[Orchestrator] Daily digest sent")
        except Exception as e:
            logger.error(f"[Orchestrator] Daily digest failed: {e}")
    
    # Mark queued notifications as sent
    await _db.notification_queue.update_many(
        {'sent': False},
        {'$set': {
            'sent': True,
            'sent_at': datetime.now(timezone.utc)
        }}
    )


# ══════════════════════════════════════════════════════════════════
# APPROVAL HANDLERS
# ══════════════════════════════════════════════════════════════════

async def handle_approval(event_id: str, approved: bool, admin_note: str = ''):
    """Handle approval/rejection from WhatsApp or dashboard."""
    if _db is None:
        return {'error': 'Database not ready'}
    
    status = 'approved' if approved else 'rejected'
    
    # Update pending approval
    result = await _db.pending_approvals.update_one(
        {'event_id': {'$regex': f'^{event_id}'}},
        {'$set': {
            'status': status,
            'admin_note': admin_note,
            'resolved_at': datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.modified_count == 0:
        return {'error': 'Approval not found'}
    
    # Update corresponding event
    await _db.orchestrator_events.update_one(
        {'event_id': {'$regex': f'^{event_id}'}},
        {'$set': {
            'status': f'{status}_by_admin',
            'admin_note': admin_note
        }}
    )
    
    logger.info(f"[Orchestrator] Event {event_id} {status} by admin")
    return {'status': status, 'event_id': event_id}


async def get_pending_approvals():
    """Get all pending approvals for dashboard."""
    if _db is None:
        return []
    
    approvals = await _db.pending_approvals.find(
        {'status': 'pending'},
        {'_id': 0}
    ).sort('created_at', -1).to_list(50)
    
    return approvals


async def get_recent_events(limit: int = 50):
    """Get recent orchestrator events for dashboard."""
    if _db is None:
        return []
    
    events = await _db.orchestrator_events.find(
        {},
        {'_id': 0}
    ).sort('created_at', -1).limit(limit).to_list(limit)
    
    return events


async def get_orchestrator_stats():
    """Get stats for dashboard."""
    if _db is None:
        return {}
    
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    
    events = await _db.orchestrator_events.find(
        {'created_at': {'$gte': since_24h}},
        {'status': 1, 'type': 1}
    ).to_list(None)
    
    pending = await _db.pending_approvals.count_documents({'status': 'pending'})
    queued = await _db.notification_queue.count_documents({'sent': False})
    
    return {
        'events_24h': len(events),
        'auto_handled': len([e for e in events if e.get('status') in ['auto_fixed', 'restarted', 'blocked', 'queued_for_digest']]),
        'crashes': len([e for e in events if e.get('type') == 'crash']),
        'violations': len([e for e in events if e.get('type') == 'violation']),
        'pending_approvals': pending,
        'queued_notifications': queued
    }
