---
name: Discord command naming
description: Discord application command naming constraints relevant to slash-command registration.
---

Discord application-command names are required to be lowercase by Discord and
by discord.py's command validator. An uppercase slash-command spelling cannot
be registered as a native application command.

**Why:** Attempting to construct an uppercase `app_commands.Command` fails
before synchronization, so the bot would not start.

**How to apply:** Use the lowercase equivalent in code and explain the
platform limitation in user-facing setup documentation when a requested
command contains uppercase letters.