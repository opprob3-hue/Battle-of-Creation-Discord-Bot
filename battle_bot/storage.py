from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Iterable

from .models import BattleState
from .settings import STATE_FILE


class BattleStore:
    """Small atomic JSON store so a bot restart does not erase active battles."""

    def __init__(self, path: Path = STATE_FILE) -> None:
        self.path = path
        self._lock = asyncio.Lock()
        self._states: dict[int, BattleState] = {}

    async def load(self) -> dict[int, BattleState]:
        async with self._lock:
            if not self.path.exists():
                self._states = {}
                return self._states.copy()
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self._states = {
                    int(guild_id): BattleState.from_dict(state)
                    for guild_id, state in (raw.get("battles") or {}).items()
                }
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                # Preserve a corrupt file for diagnosis rather than silently
                # deleting it. The in-memory store starts clean and can be
                # replaced by the next successful save.
                self._states = {}
            return self._states.copy()

    async def get(self, guild_id: int) -> BattleState | None:
        async with self._lock:
            return self._states.get(guild_id)

    async def save(self, state: BattleState) -> None:
        async with self._lock:
            self._states[state.guild_id] = state
            self._write_locked()

    async def delete(self, guild_id: int) -> None:
        async with self._lock:
            self._states.pop(guild_id, None)
            self._write_locked()

    async def active_states(self) -> list[BattleState]:
        async with self._lock:
            return [state for state in self._states.values() if state.is_active()]

    def _write_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "battles": {
                str(guild_id): state.to_dict()
                for guild_id, state in self._states.items()
            },
        }
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
