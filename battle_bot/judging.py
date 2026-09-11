om __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass

from google import genai
from google.genai import types

from .models import Player
from .settings import AI_JUDGE_TIMEOUT_SECONDS


LOGGER = logging.getLogger("battle_of_creation.judging")
_AI_SEMAPHORE = asyncio.Semaphore(3)


@dataclass(frozen=True)
class Judgement:
    winner_id: int
    loser_id: int
    reason: str


_POWER_WORDS = {
    "battle",
    "blade",
    "boss",
    "combat",
    "dragon",
    "fighter",
    "god",
    "king",
    "magic",
    "power",
    "sword",
    "warrior",
}
_CHAOS_WORDS = {"chaos", "cat", "funny", "meow", "monster", "nine", "tail", "tails"}


def _score(player: Player) -> tuple[int, int]:
    words = re.findall(r"[a-z0-9]+", player.submission.lower())
    power = sum(4 for word in words if word in _POWER_WORDS)
    creative = min(len(set(words)), 8)
    length_signal = min(len(player.submission.strip()), 40) // 8
    # A stable tie-breaker makes the no-AI judge reproducible after a restart.
    tie_break = int(hashlib.sha256(
        f"{player.user_id}:{player.submission.casefold()}".encode("utf-8")
    ).hexdigest()[:8], 16) % 7
    return power + creative + length_signal, tie_break


def _submission_signal(submission: str) -> str:
    words = re.findall(r"[a-z0-9]+", submission.lower())
    if any(word in _POWER_WORDS for word in words):
        return "stronger battle-ready wording"
    if any(word in _CHAOS_WORDS for word in words):
        return "a memorable chaos factor"
    if len(set(words)) >= 3:
        return "a more detailed concept"
    if len(submission) >= 12:
        return "a clearer overall identity"
    return "a sharp, instantly readable identity"


def _variant_index(player_one: Player, player_two: Player, round_number: int) -> int:
    seed = (
        f"{round_number}:{player_one.user_id}:{player_one.submission.casefold()}:"
        f"{player_two.user_id}:{player_two.submission.casefold()}"
    )
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % 8


def _ensure_both_submissions_in_reason(
    reason: str,
    winner: Player,
    loser: Player,
) -> str:
    reason = " ".join(reason.strip().split())
    if not reason:
        return ""
    if winner.submission.casefold() not in reason.casefold():
        reason = f"{winner.submission} wins because {reason}"
    if loser.submission.casefold() not in reason.casefold():
        reason = f"{reason} It overcame {loser.submission} in this matchup."
    return reason[:950]


def judge_match(
    player_one: Player,
    player_two: Player,
    round_number: int = 0,
) -> Judgement:
    score_one = _score(player_one)
    score_two = _score(player_two)
    if score_one > score_two or score_one == score_two and player_one.user_id < player_two.user_id:
        winner, loser = player_one, player_two
    else:
        winner, loser = player_two, player_one

    winner_submission = winner.submission
    loser_submission = loser.submission
    signal = _submission_signal(winner_submission)
    close = abs(sum(score_one) - sum(score_two)) <= 2
    logical = (
        f"{winner_submission} gets the edge over {loser_submission} because it showed "
        f"{signal} and a stronger overall matchup profile."
    )
    funny_bits = (
        "The judge gave it the tiny crown and told the other choice to update its "
        "battle résumé 😭",
        "Basically, the arena heard that submission and immediately turned the "
        "dramatic music up 😭",
        "The loser still had serious main-character energy, but the scoreboard "
        "had already chosen violence—in the harmless tournament sense 😭",
        "One choice brought the strategy; the other accidentally brought a very "
        "confident reaction image 😭",
        "The matchup was close enough to need a replay, but the winner's imaginary "
        "entrance fireworks settled the argument 😭",
        "That is the sort of result that makes the defeated submission stare at "
        "the bracket like it has personally betrayed them 😭",
        "The winner walked in with a plan; the loser walked in with excellent "
        "plot-twist potential 😭",
        "The arena committee has reviewed the evidence and confiscated the loser's "
        "victory music for now 😭",
    )
    funny = funny_bits[_variant_index(player_one, player_two, round_number)]
    reason = f"{logical} {funny}"
    if close:
        reason = (
            f"{winner_submission} narrowly edges {loser_submission}: {signal} gave it "
            f"the logical advantage, even though both choices made this a genuinely "
            f"close call. {funny}"
        )
    return Judgement(winner_id=winner.user_id, loser_id=loser.user_id, reason=reason)


async def judge_match_with_ai(
    player_one: Player,
    player_two: Player,
    round_number: int,
) -> Judgement:
    """Use AI for fresh matchup commentary, with a deterministic local fallback."""
    local_judgement = judge_match(player_one, player_two, round_number)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return local_judgement

    prompt = f"""
You are the judge for a friendly Discord tournament called Battle of Creation.
Compare these two submissions and choose a winner. Use general knowledge when
helpful, but do not invent precise facts you are unsure about.

Submission one: {player_one.submission}
Submission two: {player_two.submission}

Rules:
- Choose exactly one winner. The winner must be either "one" or "two".
- Write one fresh reason of 2-4 sentences.
- Make the reason approximately 50% logical comparison and 50% playful humor.
- Mention both exact submission names in the reason.
- Explain why the winner has the advantage in this specific matchup.
- Be friendly. No hateful, discriminatory, threatening, or genuinely insulting content.
- Do not reuse a stock sentence or say "it is stronger overall" without explaining why.
- Return only valid JSON: {{"winner":"one"|"two","reason":"..."}}
"""

    try:
        async with _AI_SEMAPHORE:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=AI_JUDGE_TIMEOUT_SECONDS * 1000,
                ),
            )
            try:
                response = await client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        max_output_tokens=8192,
                    ),
                )
            finally:
                await client.aio.aclose()
        content = response.text or ""
        data = json.loads(content)
        winner_choice = str(data.get("winner", "")).lower().strip()
        raw_reason = str(data.get("reason", "")).strip()
        if winner_choice == "one":
            winner, loser = player_one, player_two
        elif winner_choice == "two":
            winner, loser = player_two, player_one
        else:
            return local_judgement
        reason = _ensure_both_submissions_in_reason(raw_reason, winner, loser)
        if len(reason) < 30:
            return local_judgement
        return Judgement(winner_id=winner.user_id, loser_id=loser.user_id, reason=reason)
    except Exception as error:
        LOGGER.warning("AI judge unavailable; using local judge: %s", type(error).__name__)
        return local_judgementof winning the battle.

ORIGINAL CREATIONS:

If someone submits an original character, object, animal, or concept,
only use abilities that the user actually provides.

Do not invent extra powers.

However, do NOT reward the user for writing a huge description.

Example:

"Bob can destroy a planet."

should not automatically lose to:

"Bob can destroy a planet, has 500 words describing himself..."

The second submission only wins if the additional ACTUAL ABILITIES
make it stronger.

REAL PEOPLE / NORMAL OBJECTS / ANIMALS:

Use realistic capabilities unless the submission is explicitly fictional
or supernatural.

Do not randomly give normal objects or animals supernatural powers.

AI JUDGING:

Use the existing Gemini API integration if GEMINI_API_KEY is available.

Keep the API key in the environment variable:
GEMINI_API_KEY

NEVER hardcode the API key into the source code.

The Gemini judge should receive both submissions and determine the winner
using the power rules above.

If Gemini is unavailable, keep a deterministic local fallback judge so
the bot can still function.

The local fallback must NOT use description length or description detail
as a scoring advantage.

LOCAL FALLBACK PRIORITY:

1. Actual power/abilities
2. Attack/destructive capability
3. Speed
4. Durability
5. Hax/special abilities
6. Range
7. Stamina
8. Combat ability
9. Established power profiles/known characters

Do NOT use:
- word count
- description length
- number of unique words
- writing quality
- creativity score based on text length

REASON:

After every battle, show the winner and explain WHY they won.

Use the actual submission names, NOT P1, P2, P3, etc.

Example:

🏆 Ichigo wins over Hen

Reason:
Ichigo has the stronger overall combat power, speed, durability and
abilities in this matchup. Hen had some useful tricks, but the power gap
was too much. Bro brought confidence to a cosmic-level fight 💀

The reason should be approximately:
50% logical
50% funny/playful.

The humor must not replace the actual explanation.

The reason MUST explain the power advantage.

Do not say:
"X wins because the description is more detailed."

Do not say:
"X wins because they have more words."

Do not judge writing quality.

OUTPUT:

Keep the existing Discord embed/battle formatting.

The result should look roughly like:

🏆 ROUND 1 RESULT

Ichigo wins over Hen

Reason:
[actual power-based explanation + funny comment]

IMPORTANT:
Make sure the code still works with the existing models,
storage, round system, Discord interactions, buttons, modals,
player assignment, and battle flow.

Do not remove existing functionality just to implement this change.

After modifying the code, make sure there are no syntax errors and
that the bot can start normally with the existing
