# Battle of Creation Discord Bot

An isolated Python `discord.py` tournament bot with two slash commands for
server-specific, avatar-based Battle of Creation brackets.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string
- `python -m battle_bot.bot` — run the Battle of Creation Discord bot
- Required secret: `DISCORD_TOKEN`

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

_Populate as you build — short repo map plus pointers to the source-of-truth file for DB schema, API contracts, theme files, etc._

## Architecture decisions

_Populate as you build — non-obvious choices a reader couldn't infer from the code (3-5 bullets)._

## Product

The bot lets Discord members submit any creation, enter a fair 2–8 player
single-elimination bracket, and see generated versus cards using their Discord
avatars. Active state is isolated per server and persisted across restarts.

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- The bot requires the Server Members Intent in Discord Developer Portal.
- State is stored in `data/battle_state.json`; it is intentionally separate
  from the existing TypeScript API and canvas artifacts.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
