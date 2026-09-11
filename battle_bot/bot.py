from __future__ import annotations

import asyncio
import logging
import os
from typing import Iterable

import discord
from discord import app_commands
from discord.ext import commands

from .image_cards import create_battle_card, create_battle_banner
from .judging import judge_match
from .models import BattleState, Match, Player
from .settings import (
    BOT_TOKEN_ENV,
    MAX_PLAYERS,
    MESSAGE_DELAY_SECONDS,
    MIN_PLAYERS,
)
from .storage import BattleStore
from .views import BattleView


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger("battle_of_creation")


def safe_text(value: str, limit: int = 180) -> str:
    value = discord.utils.escape_mentions(discord.utils.escape_markdown(value.strip()))
    return value[:limit] + ("…" if len(value) > limit else "")


def mention(user_id: int) -> str:
    return f"<@{user_id}>"


class BattleBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        # This bot intentionally exposes slash commands only; no message
        # content intent or legacy prefix commands are needed.
        super().__init__(command_prefix=[], intents=intents)
        self.store = BattleStore()
        self._guild_locks: dict[int, asyncio.Lock] = {}
        self._running_tasks: dict[int, asyncio.Task[None]] = {}
        self._ready_once = False

    def guild_lock(self, guild_id: int) -> asyncio.Lock:
        return self._guild_locks.setdefault(guild_id, asyncio.Lock())

    async def get_state(self, guild_id: int) -> BattleState | None:
        return await self.store.get(guild_id)

    async def setup_hook(self) -> None:
        await self.store.load()
        self.tree.add_command(start_battle_command)
        self.tree.add_command(cancel_battle_command)
        await self.tree.sync()

    async def on_ready(self) -> None:
        if self.user:
            LOGGER.info("Connected as %s (%s)", self.user, self.user.id)
        if self._ready_once:
            return
        self._ready_once = True
        for state in await self.store.active_states():
            if state.status == "joining":
                self.add_view(BattleView(self, state.guild_id), message_id=state.message_id)
            elif state.status == "running":
                self._schedule_battle(state.guild_id)

    async def on_member_remove(self, member: discord.Member) -> None:
        state = await self.store.get(member.guild.id)
        if not state or not state.is_active():
            return
        if member.id not in state.players:
            return
        if state.status == "joining":
            async with self.guild_lock(member.guild.id):
                state.players.pop(member.id, None)
                await self.store.save(state)
            await self.refresh_main_message(state)
            return
        # A running match checks membership before it is judged. This event
        # only persists the change so a restart cannot reintroduce the player.
        player = state.players[member.id]
        player.eliminated = True
        if member.id not in state.eliminated_players:
            state.eliminated_players.append(member.id)
        await self.store.save(state)

    async def handle_submission(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        choice: str,
    ) -> None:
        if not interaction.guild or interaction.guild.id != guild_id:
            await interaction.response.send_message("❌ This battle belongs to another server.", ephemeral=True)
            return
        async with self.guild_lock(guild_id):
            state = await self.store.get(guild_id)
            if not state or state.status != "joining":
                await interaction.response.send_message(
                    "❌ This battle is no longer accepting submissions.",
                    ephemeral=True,
                )
                return
            if interaction.user.id in state.players:
                await interaction.response.send_message(
                    "❌ You already submitted to this battle.",
                    ephemeral=True,
                )
                return
            if len(state.players) >= MAX_PLAYERS:
                await interaction.response.send_message(
                    "❌ This battle is full (8/8 players).",
                    ephemeral=True,
                )
                return
            user = interaction.user
            player = Player(
                user_id=user.id,
                username=user.name,
                display_name=getattr(user, "display_name", user.name),
                avatar_url=str(user.display_avatar.url),
                submission=choice,
            )
            state.players[user.id] = player
            await self.store.save(state)

        await interaction.response.send_message("✅ Your submission is locked in.", ephemeral=True)
        await self._send_channel_message(
            interaction.channel,
            f"📥 {interaction.user.mention} joined the battle!",
        )
        await self.refresh_main_message(state)

    async def handle_start(self, interaction: discord.Interaction, guild_id: int) -> None:
        if not interaction.guild or interaction.guild.id != guild_id:
            await interaction.response.send_message("❌ This battle belongs to another server.", ephemeral=True)
            return
        async with self.guild_lock(guild_id):
            state = await self.store.get(guild_id)
            if not state or state.status != "joining":
                await interaction.response.send_message(
                    "❌ There is no active Battle of Creation accepting players.",
                    ephemeral=True,
                )
                return
            if len(state.players) < MIN_PLAYERS:
                await interaction.response.send_message(
                    "❌ At least 2 players are required to start the battle.",
                    ephemeral=True,
                )
                return
            removed = await self._remove_players_who_left(interaction.guild, state)
            if len(state.players) < MIN_PLAYERS:
                await self.store.save(state)
                await interaction.response.send_message(
                    "❌ At least 2 active players are required to start the battle.",
                    ephemeral=True,
                )
                await self.refresh_main_message(state)
                return
            state.status = "running"
            state.current_round = 0
            state.current_matches = []
            state.bye_players = []
            await self.store.save(state)

        await interaction.response.send_message(
            "⚔️ The battle is locked in. No new players can join.",
            ephemeral=True,
        )
        await self.refresh_main_message(state)
        self._schedule_battle(guild_id)

    async def handle_ui_error(self, interaction: discord.Interaction, error: Exception) -> None:
        LOGGER.exception("Discord UI interaction failed", exc_info=error)
        message = "❌ Something went wrong while handling that action."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def refresh_main_message(self, state: BattleState) -> None:
        if not state.message_id:
            return
        channel = self.get_channel(state.channel_id)
        if not isinstance(channel, discord.TextChannel):
            try:
                channel = await self.fetch_channel(state.channel_id)
            except (discord.HTTPException, discord.NotFound):
                return
        try:
            message = await channel.fetch_message(state.message_id)
            view = BattleView(self, state.guild_id) if state.status == "joining" else None
            embed = build_main_embed(state)
            banner = create_battle_banner()
            embed.set_thumbnail(url="attachment://battle-banner.png")
            await message.edit(
                embed=embed,
                view=view,
                attachments=[discord.File(banner, filename="battle-banner.png")],
            )
        except (discord.HTTPException, discord.NotFound):
            LOGGER.warning("Could not update Battle of Creation message %s", state.message_id)

    async def _remove_players_who_left(self, guild: discord.Guild, state: BattleState) -> int:
        removed = 0
        for user_id in list(state.players):
            try:
                await guild.fetch_member(user_id)
            except discord.NotFound:
                state.players.pop(user_id, None)
                removed += 1
            except discord.HTTPException:
                # A transient fetch failure must not eject a valid player.
                continue
        return removed

    async def _send_channel_message(
        self,
        channel: discord.abc.Messageable | None,
        content: str,
        *,
        embed: discord.Embed | None = None,
        file: discord.File | None = None,
    ) -> discord.Message | None:
        if channel is None:
            return None
        try:
            return await channel.send(content, embed=embed, file=file)
        except discord.HTTPException:
            LOGGER.exception("Could not send battle message")
            return None

    def _schedule_battle(self, guild_id: int) -> None:
        task = self._running_tasks.get(guild_id)
        if task and not task.done():
            return
        self._running_tasks[guild_id] = asyncio.create_task(self._run_battle(guild_id))

    async def _run_battle(self, guild_id: int) -> None:
        try:
            state = await self.store.get(guild_id)
            if not state or state.status != "running":
                return
            while state.status == "running":
                if not state.current_matches:
                    self._prepare_next_round(state)
                    await self.store.save(state)
                    await self._announce_byes(state)
                for battle_match in state.current_matches:
                    if battle_match.status == "done":
                        continue
                    await self._run_match(state, battle_match)
                    await self.store.save(state)
                    await asyncio.sleep(MESSAGE_DELAY_SECONDS)
                survivors = [
                    match.winner_id
                    for match in state.current_matches
                    if match.winner_id is not None
                ] + state.bye_players
                survivors = list(dict.fromkeys(survivors))
                if len(survivors) == 1:
                    champion_id = survivors[0]
                    state.champion_id = champion_id
                    state.status = "completed"
                    state.current_matches = []
                    state.bye_players = []
                    state.players[champion_id].won = True
                    await self.store.save(state)
                    await self._announce_champion(state)
                    await self.refresh_main_message(state)
                    return
                state.current_matches = []
                state.bye_players = []
                await self.store.save(state)
                await asyncio.sleep(MESSAGE_DELAY_SECONDS)
                state = await self.store.get(guild_id)
                if not state:
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Battle task failed for guild %s", guild_id)
            state = await self.store.get(guild_id)
            if state and state.status == "running":
                # Keep the exact pending match on disk so a later restart or
                # manual recovery does not silently discard the tournament.
                state.status = "joining"
                await self.store.save(state)
                await self.refresh_main_message(state)
        finally:
            self._running_tasks.pop(guild_id, None)

    def _prepare_next_round(self, state: BattleState) -> None:
        state.current_round += 1
        entrants = state.active_player_ids()
        state.bye_players = []
        state.current_matches = []
        for user_id in entrants:
            state.players[user_id].current_round = state.current_round
        if len(entrants) % 2:
            state.bye_players.append(entrants[-1])
            entrants = entrants[:-1]
        state.current_matches = [
            Match(
                player_one_id=entrants[index],
                player_two_id=entrants[index + 1],
                round_number=state.current_round,
            )
            for index in range(0, len(entrants), 2)
        ]

    async def _announce_byes(self, state: BattleState) -> None:
        if not state.bye_players:
            return
        bye_lines = "\n".join(
            f"{mention(user_id)} ({safe_text(state.players[user_id].display_name)})"
            for user_id in state.bye_players
        )
        await self._send_state_message(
            state,
            f"⚔️ Round {state.current_round}\n\n{bye_lines}, see you next round 👀",
        )
        await asyncio.sleep(MESSAGE_DELAY_SECONDS)

    async def _run_match(self, state: BattleState, battle_match: Match) -> None:
        first = state.players.get(battle_match.player_one_id)
        second = state.players.get(battle_match.player_two_id)
        if not first or not second:
            return
        if first.eliminated or second.eliminated:
            winner = second if first.eliminated else first
            loser = first if first.eliminated else second
            await self._finish_match(state, battle_match, winner, loser, "left the server")
            return
        card = await create_battle_card(first, second)
        embed = discord.Embed(
            title=f"⚔️ Round {battle_match.round_number}",
            description=(
                f"{mention(first.user_id)}\n**{safe_text(first.submission)}**\n\n"
                f"**VS**\n\n"
                f"{mention(second.user_id)}\n**{safe_text(second.submission)}**"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Battle of Creation")
        if card:
            embed.set_image(url="attachment://battle-card.png")
            await self._send_state_message(
                state,
                "Let's start it now...",
                embed=embed,
                file=discord.File(card, filename="battle-card.png"),
            )
        else:
            embed.set_thumbnail(url=first.avatar_url)
            embed.set_image(url=second.avatar_url)
            await self._send_state_message(state, "Let's start it now...", embed=embed)
        await asyncio.sleep(MESSAGE_DELAY_SECONDS)
        if first.eliminated or second.eliminated:
            winner = second if first.eliminated else first
            loser = first if first.eliminated else second
            await self._finish_match(state, battle_match, winner, loser, "left the server")
            return
        judgement = judge_match(first, second)
        winner = state.players[judgement.winner_id]
        loser = state.players[judgement.loser_id]
        await self._finish_match(state, battle_match, winner, loser, judgement.reason)

    async def _finish_match(
        self,
        state: BattleState,
        battle_match: Match,
        winner: Player,
        loser: Player,
        reason: str,
    ) -> None:
        battle_match.status = "done"
        battle_match.winner_id = winner.user_id
        battle_match.loser_id = loser.user_id
        winner.won = True
        loser.eliminated = True
        if winner.user_id not in state.winners:
            state.winners.append(winner.user_id)
        if loser.user_id not in state.eliminated_players:
            state.eliminated_players.append(loser.user_id)
        if reason == "left the server":
            reason_text = (
                f"{mention(winner.user_id)} advances because {safe_text(loser.display_name)} "
                "left the server before the matchup could finish."
            )
        else:
            reason_text = reason
        embed = discord.Embed(
            title=f"🏆 Round {battle_match.round_number} Result",
            description=(
                f"{mention(winner.user_id)}\n**{safe_text(winner.submission)}**\n\n"
                "**Winner!**\n\n"
                f"**Reason:** {safe_text(reason_text, 1000)}"
            ),
            color=discord.Color.gold(),
        )
        await self._send_state_message(state, "Let's see... who wins?? 👀", embed=embed)

    async def _announce_champion(self, state: BattleState) -> None:
        if state.champion_id is None:
            return
        champion = state.players[state.champion_id]
        embed = discord.Embed(
            title="👑 BATTLE OF CREATION CHAMPION",
            description=(
                f"{mention(champion.user_id)} — **{safe_text(champion.display_name)}**\n\n"
                f"**{safe_text(champion.submission)}** takes the whole tournament!"
            ),
            color=discord.Color.green(),
        )
        await self._send_state_message(state, "The tournament is over!", embed=embed)

    async def _send_state_message(
        self,
        state: BattleState,
        content: str,
        *,
        embed: discord.Embed | None = None,
        file: discord.File | None = None,
    ) -> discord.Message | None:
        channel = self.get_channel(state.channel_id)
        if not channel:
            try:
                channel = await self.fetch_channel(state.channel_id)
            except (discord.HTTPException, discord.NotFound):
                return None
        return await self._send_channel_message(channel, content, embed=embed, file=file)


def build_main_embed(state: BattleState) -> discord.Embed:
    description = (
        "Submit anything you want, then battle through a fair bracket. "
        "Only winners advance until one creation takes the crown."
    )
    embed = discord.Embed(
        title="⚔️ BATTLE OF CREATION",
        description=description,
        color=discord.Color.from_rgb(105, 67, 211),
    )
    embed.add_field(
        name="How it works",
        value="Click **📝 Submit**, enter any creation, and press **▶️ Start** when at least two players are ready.",
        inline=False,
    )
    embed.add_field(name="Players", value=f"👥 Players: {len(state.players)}/{MAX_PLAYERS}", inline=True)
    embed.add_field(name="Status", value="Accepting players" if state.status == "joining" else "Battle locked", inline=True)
    if state.players:
        roster = "\n".join(
            f"• {safe_text(player.display_name)} — {safe_text(player.submission, 80)}"
            for player in state.players.values()
        )
        embed.add_field(name="Current roster", value=roster[:1024], inline=False)
    else:
        embed.add_field(name="Current roster", value="No submissions yet. Be the first to enter.", inline=False)
    if state.main_image_url:
        embed.set_thumbnail(url=state.main_image_url)
    embed.set_footer(text="Maximum 8 players • No uploads required")
    return embed


async def start_battle_command(interaction: discord.Interaction) -> None:
    if not interaction.guild or not interaction.channel:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return
    bot = interaction.client
    if not isinstance(bot, BattleBot):
        await interaction.response.send_message("❌ Battle system is unavailable.", ephemeral=True)
        return
    guild_id = interaction.guild.id
    async with bot.guild_lock(guild_id):
        existing = await bot.store.get(guild_id)
        if existing and existing.is_active():
            await interaction.response.send_message(
                "❌ There is already an active Battle of Creation in this server.",
                ephemeral=True,
            )
            return
        state = BattleState(guild_id=guild_id, channel_id=interaction.channel.id)
        banner = create_battle_banner()
        embed = build_main_embed(state)
        embed.set_thumbnail(url="attachment://battle-banner.png")
        await interaction.response.send_message(
            embed=embed,
            file=discord.File(banner, filename="battle-banner.png"),
            view=BattleView(bot, guild_id),
        )
        message = await interaction.original_response()
        state.message_id = message.id
        # The banner is reattached when the main message is edited, so the
        # attachment URL never has to be persisted as a stale CDN reference.
        state.main_image_url = None
        await bot.store.save(state)


async def cancel_battle_command(interaction: discord.Interaction) -> None:
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return
    bot = interaction.client
    if not isinstance(bot, BattleBot):
        await interaction.response.send_message("❌ Battle system is unavailable.", ephemeral=True)
        return
    guild_id = interaction.guild.id
    async with bot.guild_lock(guild_id):
        state = await bot.store.get(guild_id)
        if not state or not state.is_active():
            await interaction.response.send_message(
                "❌ There is no active Battle of Creation.",
                ephemeral=True,
            )
            return
        task = bot._running_tasks.get(guild_id)
        if task and not task.done():
            task.cancel()
        await bot.store.delete(guild_id)
    await interaction.response.send_message("🛑 Battle of Creation cancelled.")


start_battle_command = app_commands.Command(
    # Discord requires application command names to be lowercase. The
    # requested uppercase spelling cannot be registered by Discord/discord.py.
    name="start_battle_of_creation",
    description="Start a Battle of Creation tournament",
    callback=start_battle_command,
)
cancel_battle_command = app_commands.Command(
    name="cancel_battle_of_creation",
    description="Cancel the active Battle of Creation tournament",
    callback=cancel_battle_command,
)


def main() -> None:
    token = os.getenv(BOT_TOKEN_ENV)
    if not token:
        raise RuntimeError(f"{BOT_TOKEN_ENV} secret is required to run the Discord bot.")
    bot = BattleBot()
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
