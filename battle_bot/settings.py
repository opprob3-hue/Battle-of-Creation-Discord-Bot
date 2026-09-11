from __future__ import annotations

import os
from pathlib import Path


BOT_TOKEN_ENV = "DISCORD_TOKEN"
STATE_FILE = Path(os.getenv("BATTLE_STATE_FILE", "data/battle_state.json"))

MAX_PLAYERS = 8
MIN_PLAYERS = 2
MESSAGE_DELAY_SECONDS = 5
SUBMISSION_MAX_LENGTH = 200
AI_JUDGE_TIMEOUT_SECONDS = 8
