# Scout Scan Skill
## Trigger intent
User asks to scan, check, or research a business website or lead.
Keywords: scan, website, check site, research business, what does their site say, find leads.
## Owner Agent
Scout / Hunter — shared/agents/hunter_ora.py
## What ORA does
Delegate to Scout Agent (HunterORA.run_cycle).
Return scan summary in 3 bullets:
- What the business does
- What's missing/broken on their site
- Recommended AUREM fix
## Tone
Professional analyst. Factual. No fluff.
