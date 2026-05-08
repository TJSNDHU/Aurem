# Follow-up Check Skill
## Trigger intent
User asks about follow-up status, drip progress, lead engagement, or contact history.
Keywords: follow up, drip, contacted, how many touches, sequence, did we reach out.
## Owner Agent
Follow-up Agent — shared/agents/followup_ora.py::FollowupORA.run_cycle
## What ORA does
Delegate to Follow-up Agent for status.
Return clean timeline of: channels, dates, response status per touch.
