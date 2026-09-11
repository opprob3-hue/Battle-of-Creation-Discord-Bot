from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .models import Player


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


def judge_match(player_one: Player, player_two: Player) -> Judgement:
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
    if close:
        reason = (
            f"{winner_submission} narrowly beats {loser_submission} because both choices "
            f"had a real angle, but {winner_submission} brought {signal}. The judge saw "
            "one extra boss-fight aura and ran with it 😭"
        )
    else:
        reason = (
            f"{winner_submission} wins over {loser_submission} because the rules-based "
            f"judge found {signal} and a stronger overall matchup profile. "
            f"{loser_submission} had personality, but this round rewarded impact 😭"
        )
    return Judgement(winner_id=winner.user_id, loser_id=loser.user_id, reason=reason)
