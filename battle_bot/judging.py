Modify my existing Battle of Creation Discord bot.

IMPORTANT:
Do NOT rebuild the bot from scratch.
Do NOT remove or break any existing features.
Keep the existing Discord buttons, modals, rounds, player system, embeds,
battle flow, persistence, and commands unless a change below specifically
requires modifying them.

MAIN CHANGE:
The AI judging system must judge ACTUAL POWER, not the quality or length
of the user's description.

POWER > DESCRIPTION DETAIL.

A submission must NOT become stronger because:
- the description is longer
- the description has more words
- the description contains more detail
- the writing sounds more impressive
- the player explains it better
- the username is funny/popular

The actual abilities and capabilities of the submitted thing determine
the result.

FICTIONAL CHARACTER JUDGING:

The bot should recognize characters from many different franchises,
not just one anime.

Examples include:
Bleach
Dragon Ball
Naruto
One Piece
Jujutsu Kaisen
One Punch Man
My Hero Academia
Demon Slayer
Hunter x Hunter
JoJo's Bizarre Adventure
Chainsaw Man
Attack on Titan
Black Clover
Fairy Tail
Solo Leveling
Marvel
DC
and other recognizable fictional universes.

The user should only need to submit the name.

Example:
Ichigo
Goku
Naruto
Saitama
Gojo
Luffy

The AI judge should identify the character and their source/franchise.

For fictional characters, judge using established canon information,
including:

- Attack power
- Destructive capability
- Speed
- Reaction speed
- Strength
- Durability
- Stamina
- Regeneration/healing
- Special abilities
- Hax
- Range
- Combat skill
- Battle experience
- Canon feats
- Reliable canon scaling
- Canon transformations/forms
- Canon equipment

Use the strongest relevant CANON version unless the user specifies
a particular form.

Do NOT use fan-made feats, fan theories, memes, or unsupported claims.

Do NOT invent abilities or feats.

An ability should only matter if it can realistically affect the opponent
in that matchup.

MATCHUP LOGIC:

A character does not automatically win just because they have a higher
raw attack power.

Consider whether:
- their speed allows them to land attacks
- the opponent has a canon counter
- hax can bypass durability
- the opponent can survive or resist the ability
- range matters
- regeneration matters
- stamina matters
- the abilities actually work against the opponent

The final decision should be based on who has the stronger overall chance
of winning the battle.

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
