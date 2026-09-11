from __future__ import annotations

import discord

from .settings import MAX_PLAYERS, SUBMISSION_MAX_LENGTH


class SubmissionModal(discord.ui.Modal, title="Submit anything"):
    choice = discord.ui.TextInput(
        label="What do you choose?",
        placeholder="Anything: a character, object, animal, concept, or idea...",
        required=True,
        max_length=SUBMISSION_MAX_LENGTH,
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, bot: "BattleBotProtocol", guild_id: int) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        choice = str(self.choice.value).strip()
        if not choice:
            await interaction.response.send_message(
                "❌ Your submission cannot be empty.",
                ephemeral=True,
            )
            return
        await self.bot.handle_submission(interaction, self.guild_id, choice)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        await self.bot.handle_ui_error(interaction, error)


class BattleView(discord.ui.View):
    """Persistent controls for one guild's active battle."""

    def __init__(self, bot: "BattleBotProtocol", guild_id: int) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.add_item(
            discord.ui.Button(
                label="📝 Submit",
                style=discord.ButtonStyle.primary,
                custom_id=f"battle:submit:{guild_id}",
            )
        )
        self.add_item(
            discord.ui.Button(
                label="▶️ Start",
                style=discord.ButtonStyle.success,
                custom_id=f"battle:start:{guild_id}",
            )
        )
        self.children[0].callback = self._submit_callback
        self.children[1].callback = self._start_callback

    async def _submit_callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message("❌ This battle belongs to another server.", ephemeral=True)
            return
        state = await self.bot.get_state(self.guild_id)
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
        await interaction.response.send_modal(SubmissionModal(self.bot, self.guild_id))

    async def _start_callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message("❌ This battle belongs to another server.", ephemeral=True)
            return
        await self.bot.handle_start(interaction, self.guild_id)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[object],
    ) -> None:
        await self.bot.handle_ui_error(interaction, error)


class BattleBotProtocol:
    """Structural typing helper without importing the bot module at runtime."""

    async def get_state(self, guild_id: int): ...

    async def handle_submission(self, interaction: discord.Interaction, guild_id: int, choice: str): ...

    async def handle_start(self, interaction: discord.Interaction, guild_id: int): ...

    async def handle_ui_error(self, interaction: discord.Interaction, error: Exception): ...
