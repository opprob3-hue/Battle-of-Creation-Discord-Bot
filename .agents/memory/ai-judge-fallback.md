---
name: AI judge fallback
description: Reliability rule for optional AI-generated tournament commentary.
---

Managed Replit AI setup can be unavailable when the account does not support
the integration tier. The battle system should treat AI commentary as
optional, use a direct provider key only when the user supplies one securely,
and always retain a local judge that can finish the tournament.

**Why:** A battle should not stall or require an AI provider just to produce a
result, while users who opt into AI still benefit from fresh commentary.

**How to apply:** Bound AI calls with a short timeout and a concurrency limit,
validate the returned winner/reason, and fall back to varied
matchup-specific local explanations on any error.