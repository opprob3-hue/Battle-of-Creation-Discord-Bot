from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Player:
    user_id: int
    username: str
    display_name: str
    avatar_url: str
    submission: str
    won: bool = False
    eliminated: bool = False
    current_round: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Player":
        return cls(
            user_id=int(data["user_id"]),
            username=str(data.get("username") or data.get("display_name") or "Unknown user"),
            display_name=str(data.get("display_name") or data.get("username") or "Unknown user"),
            avatar_url=str(data.get("avatar_url") or ""),
            submission=str(data.get("submission") or ""),
            won=bool(data.get("won", False)),
            eliminated=bool(data.get("eliminated", False)),
            current_round=int(data.get("current_round", 0)),
        )


@dataclass
class Match:
    player_one_id: int
    player_two_id: int
    round_number: int
    status: str = "pending"
    winner_id: int | None = None
    loser_id: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Match":
        return cls(
            player_one_id=int(data["player_one_id"]),
            player_two_id=int(data["player_two_id"]),
            round_number=int(data["round_number"]),
            status=str(data.get("status", "pending")),
            winner_id=int(data["winner_id"]) if data.get("winner_id") is not None else None,
            loser_id=int(data["loser_id"]) if data.get("loser_id") is not None else None,
        )


@dataclass
class BattleState:
    guild_id: int
    channel_id: int
    message_id: int | None = None
    main_image_url: str | None = None
    status: str = "joining"
    current_round: int = 0
    players: dict[int, Player] = field(default_factory=dict)
    current_matches: list[Match] = field(default_factory=list)
    bye_players: list[int] = field(default_factory=list)
    winners: list[int] = field(default_factory=list)
    eliminated_players: list[int] = field(default_factory=list)
    champion_id: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BattleState":
        players = {
            int(user_id): Player.from_dict(player)
            for user_id, player in (data.get("players") or {}).items()
        }
        return cls(
            guild_id=int(data["guild_id"]),
            channel_id=int(data["channel_id"]),
            message_id=int(data["message_id"]) if data.get("message_id") is not None else None,
            main_image_url=data.get("main_image_url"),
            status=str(data.get("status", "joining")),
            current_round=int(data.get("current_round", 0)),
            players=players,
            current_matches=[Match.from_dict(match) for match in data.get("current_matches", [])],
            bye_players=[int(user_id) for user_id in data.get("bye_players", [])],
            winners=[int(user_id) for user_id in data.get("winners", [])],
            eliminated_players=[int(user_id) for user_id in data.get("eliminated_players", [])],
            champion_id=int(data["champion_id"]) if data.get("champion_id") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_active(self) -> bool:
        return self.status in {"joining", "running"}

    def active_player_ids(self) -> list[int]:
        return [
            user_id
            for user_id, player in self.players.items()
            if not player.eliminated
        ]
