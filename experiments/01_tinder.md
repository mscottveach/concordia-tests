# Experiment 01 — Tinder Recognition (the cheap version)

## The arc we're aiming for

Alice is already seated. Bob takes the only other chair because it's the
only one left. Small talk. Then Alice: *"You don't remember, do you?"*
He doesn't. Awkwardness. Turns out a year ago they were matched on
Tinder and had a disastrous first date. They blame each other at first,
then are forced to admit neither was at their best. Eventually they
wonder whether fate is giving them another shot.

## Hypothesis

If we give Alice a vivid memory of the date and Bob a hazy one — and
goals that point them in the right emotional directions — the cheap
experiment (dialogic GM, no scene structure, no mid-sim memory injection,
no chained goals) should get us at least to the recognition moment.
Maybe further. We're explicitly *not* scripting the arc; we're seeding
the conditions for it.

## Moves

### Move 1 — Alice's goal: reveal-encoded

**Was:**
> Have a genuine, curious conversation. Try to learn one real thing
> about the person across from her.

**Now:**
> Alice is almost certain the man across from her is the Bob from that
> disastrous Tinder date a year ago, but she wants to be sure before she
> says anything. She makes small talk and watches for confirmation — his
> accent, his mannerisms, anything she remembers. If she becomes sure
> it's him, she'll find a moment to ask whether he remembers her — not
> as a gotcha, but out of honest curiosity. She isn't angry. She just
> realized she wants to know how he sees that night now.

**Why:** The goal contains the *beat* ("find a moment to ask") without
scripting the *line*. The "not as a gotcha" framing keeps her from
leading with the reveal too aggressively. Third-person matches the
prompt-stack convention.

### Move 2 — Bob's goal: defensive but redeemable

**Was:**
> Be friendly but guarded. He is not in the mood to share much about
> himself unless he likes the other person.

**Now:**
> Bob is tired and came in for a quiet pint, not a conversation. He is
> polite but doesn't volunteer much; he lets the other person carry the
> talk. When something uncomfortable comes up, his first instinct is to
> deflect or rationalize — but he has a habit of eventually owning it
> when he realizes he was in the wrong.

**Why:** Bob's goal says *nothing* about Tinder — that info lives in his
memory, not his goal, so it doesn't distort his opening behavior. The
load-bearing addition is the final clause: "habit of eventually owning
it when he realizes he was in the wrong." Without that line, he'll keep
deflecting forever. With it, the framework has permission to let him
soften under pressure — which is what makes the blame-to-admission arc
possible.

### Move 3 — Alice's memory: add vivid Tinder recall

**Adding** to her existing player_specific_memories:
> A year ago Alice went on a Tinder date with a man named Bob — same
> dark hair, slight London accent, mid-forties. It was a disaster: he
> barely looked up from his phone the whole night, she got brittle and
> sarcastic in response, and they left without saying goodnight. She
> hasn't thought about him in months, but she'd recognize him anywhere.

**Why:** Vivid, specific, names-Bob. Gives her enough sensory hooks
("dark hair, slight London accent") to plausibly *recognize* the man
across from her. Crucially, it admits she contributed too ("got brittle
and sarcastic in response") — which seeds the eventual mutual admission.

### Move 4 — Bob's memory: add hazy Tinder recall

**Adding** to his existing player_specific_memories:
> Sometime last year Bob went on a Tinder date that didn't go well. He'd
> been having a brutal week at work and wasn't really present — he kept
> checking his phone, then the woman got sharp with him, and they left
> annoyed. He felt vaguely guilty afterwards but moved on. He doesn't
> remember her name or her face clearly.

**Why:** Mirrors Alice's memory but blurred — same events, no name, no
clear face. He has the *raw material* to remember once prompted but
won't volunteer it. The "wasn't really present... kept checking his
phone" gives him a concrete thing to eventually own. The "vaguely
guilty" residue means the recognition won't feel emotionally neutral
when it arrives.

### Move 5 — Bump MAX_STEPS

**Was:** 8
**Now:** 20

**Why:** The previous run ended at step 7 on the dialogic GM's own
judgment. The arc we're hoping for has more beats than that —
small-talk (2-3), reveal (1-2), blame (2-3), admission (2), fate-question
(1-2). 8 is too tight to reach the back half even if everything fires.
20 is a budget, not a goal; the GM still decides when to end.

## What we did NOT change

- **GM:** still `dialogic__GameMaster`. No scene structure, no scripted
  transitions.
- **Initializer:** still `formative_memories_initializer`, still
  `skip_formative_memories_for=["Alice", "Bob"]` — no LLM-generated
  childhoods.
- **Provider / model:** OpenRouter + `anthropic/claude-sonnet-4.6`.
- **Shared memories:** unchanged (pub, weather, table).
- **Premise:** unchanged.

## What to watch for in the log

In rough order of "if this works at all" → "if this works really well":

1. **Does Alice get to the reveal?** And in what turn?
2. **Does Bob recognize her**, or does he stay genuinely confused?
3. **Does the blame phase emerge** — even briefly?
4. **Does the mutual admission phase land**, or does Bob just sit in
   deflection?
5. **Does the "second chance / fate" reflection happen**, or does the
   GM end the scene before that?
6. **Does the dialogic GM cut things short again** like last run? If
   yes, that's a signal we need scene structure even to give the arc
   room.

## Post-run notes

(Fill in after running.)
