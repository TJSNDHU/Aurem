"""
ORA Voice Call Scripts — Outbound call scripts for AUREM acquisition campaigns.
Used by the campaign scheduler and Voice Sales Agent.
"""

SCRIPT_AUREM = {
    "greeting": (
        "Hello, may I please speak with "
        "the business owner or manager?"
    ),

    "intro": (
        "Hi {first_name}, my name is ORA. "
        "I'm calling from AUREM — "
        "we're an AI company based right "
        "here in Mississauga.\n\n"
        "I won't take more than "
        "2 minutes of your time."
    ),

    "hook_with_scan": (
        "I actually scanned your website "
        "{website} this morning and found "
        "{issues_count} issues that are "
        "affecting how you show up on Google.\n\n"
        "Your overall score was {score} "
        "out of 100.\n\n"
        "The good news is — AUREM fixes "
        "these automatically overnight, "
        "without you doing anything."
    ),

    "hook_without_scan": (
        "We work with businesses like yours "
        "in Mississauga — salons, clinics, "
        "contractors — to automate the "
        "parts of your business that eat "
        "up your time.\n\n"
        "Things like following up with "
        "leads, sending invoice reminders, "
        "and fixing your website's Google "
        "ranking — all automatic."
    ),

    "offer": (
        "We're offering a free website "
        "report for Mississauga businesses "
        "this month — no obligation at all.\n\n"
        "Can I send it to your email? "
        "It takes 30 seconds and shows "
        "you exactly what's costing you "
        "customers right now."
    ),

    "yes_response": (
        "Perfect. What's the best email "
        "for you?\n\n"
        "[COLLECT EMAIL]\n\n"
        "Great — you'll have it in the "
        "next 5 minutes.\n\n"
        "And if you like what you see, "
        "AUREM starts at $97 Canadian "
        "per month. Cancel anytime.\n\n"
        "Have a wonderful day!"
    ),

    "no_response": (
        "Absolutely no problem at all. "
        "I appreciate your time and "
        "hope you have a great day. "
        "Take care!"
    ),

    "voicemail": (
        "Hi, this is ORA calling from "
        "AUREM in Mississauga.\n\n"
        "I scanned your website and have "
        "a free report for you showing "
        "what's affecting your Google "
        "ranking.\n\n"
        "I'll send it to your email — "
        "completely free, no obligation.\n\n"
        "You can also visit aurem.live "
        "to learn more.\n\n"
        "Have a great day!"
    ),
}


def render_script(section: str, **kwargs) -> str:
    """Render a call script section with variable substitution."""
    template = SCRIPT_AUREM.get(section, "")
    try:
        return template.format(**kwargs)
    except KeyError:
        return template
