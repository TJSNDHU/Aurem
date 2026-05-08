# SEO Backlinks Skill

## Trigger intent
User asks about backlinks, unlinked mentions, SEO, sites linking to them,
or link reclamation.

Keywords: backlinks, unlinked, unlinked mentions, seo, linking to us,
mentions, reclaim, who mentions us, link building, link reclamation.

## Owner Agent
None — direct service call to `unlinked_mentions_service`.

## What ORA does
1. Resolve the business in context:
   - client portal → use `business_profiles` doc from the BIN
   - admin/chat → use the domain/business_name in the user's message or
     the most-recent lead in context
2. Call `scan_for_unlinked_mentions(business_name, website_url, db, 5)`.
3. Report back:

   ```
   Found {total} unlinked mentions for {business_name}:
     • {domain1} — "{context snippet}"
     • {domain2} — "{context snippet}"
   Want me to send outreach to reclaim these?
   ```

4. On user confirmation (yes / send / go) → call
   `send_reclamation_outreach(db, mention_id, lead)` for each pending
   mention. Reply with how many got composed + how many are queued.

## Tone
Helpful SEO advisor. Concrete numbers, no fluff. Never promise rankings.
If zero mentions → say so honestly and suggest rescanning in a week.

## Data safety
Never send outreach without explicit user confirmation. Always show the
per-mention preview first.
