# Battle of Creation bot

This isolated `discord.py` module adds these application commands:

- `/start_battle_of_creation`
- `/cancel_battle_of_creation`

Discord requires slash-command names to be lowercase, so the requested
uppercase `/START_battle_of_creation` spelling is not registerable by Discord.

The bot keeps each server's battle in `data/battle_state.json`, writes state
atomically, and restores active joining/running battles after a process restart.
The Discord token is read only from the `DISCORD_TOKEN` secret.

Run it with:

```bash
python -m battle_bot.bot
```

The bot needs the `applications.commands` scope and the Server Members Intent
enabled in the Discord Developer Portal. No AI provider or AI API key is used.
