# NotebookLM Research Skill

## Trigger intent
User asks ORA to research, deep-dive, analyze documents, or create a
research notebook.
Keywords: research, notebook, analyze docs, deep dive, create notebook,
study this, do a deep dive on, research this lead.

## Owner Agent
None — direct API call to the NotebookLM service.

## What ORA does
1. Create a temporary NotebookLM notebook keyed to the lead/topic.
2. Add the lead's website (or supplied URL) as a source.
3. Ask NotebookLM the research question from the user message.
4. Return the answer inline in chat.
5. Delete the notebook afterwards (cleanup — keeps quota clean).

## Requires
`NOTEBOOKLM_AUTH_JSON` in `.env` (Google auth blob from
`notebooklm login` output). Optional — skill degrades gracefully.

## Fallback
If not authenticated, the skill returns:
  "NotebookLM not connected. Set NOTEBOOKLM_AUTH_JSON in env to enable."

## Isolation
This skill is **not** wired into the outreach pipeline or any
auto-trigger. It fires only when ORA's skill router explicitly selects
`notebooklm_research`.
