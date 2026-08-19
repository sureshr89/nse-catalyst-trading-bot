from datetime import date

QUOTES = [
    "Protecting capital is a position too.",
    "Wait for your setup; the market owes you nothing.",
    "A good trade follows the plan, not the emotion.",
    "Risk first. Reward comes second.",
    "Consistency beats excitement.",
    "No setup is also a valid decision.",
    "Let the data confirm the trade.",
    "Small losses are the cost of staying in the game.",
    "Trade the setup, not the outcome you want.",
    "Patience is part of the strategy.",
    "A missed trade is better than a forced trade.",
    "Follow the rules when the market becomes emotional.",
    "Your edge matters only when you execute it consistently.",
    "The best trade may be no trade.",
    "Protect today's capital for tomorrow's opportunity.",
    "Process first, P&L second.",
    "Don't increase risk to recover a loss.",
    "Good entries start with good filters.",
    "Let price prove the setup.",
    "Discipline is an edge.",
    "One clean trade is better than five forced trades.",
    "Respect the stop before entering the trade.",
    "The market rewards patience more often than urgency.",
    "A strategy becomes useful when its rules are repeatable.",
    "Know your risk before you know your target.",
    "Don't confuse activity with progress.",
    "Trade only when the evidence aligns.",
    "Stay within your daily risk limit.",
    "A disciplined trader accepts uncertainty.",
    "Review the process, not just the profit.",
    "Consistency is built one controlled trade at a time.",
]


def get_daily_quote(day: date | None = None) -> str:
    day = day or date.today()
    return QUOTES[(day.timetuple().tm_yday - 1) % len(QUOTES)]
