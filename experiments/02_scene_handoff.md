# Experiment 02 — Scene-based handoff

## What went wrong in 01

Alice, with a "wait for the right moment" goal and a vivid memory of the
Tinder date, never made the reveal. 19 steps of pleasant, drifting small
talk. The dialogic GM has no concept of scene transitions, so every turn
asked her the same question with the same context — and her cautious
goal language ("she wants to be sure," "if she becomes sure") gave her
permission to hedge indefinitely.

## The hypothesis

If we force a scene transition at round 4 — pushing a new memory line
into Alice's bank (*"this is the moment to bring it up"*) and changing
the question her prompt asks (*"does anything click?"*) — she will
reveal. The reveal isn't triggered by her *deciding* to act; it's
triggered by the prompt itself changing in a specific, pointed way.

## The pivot from what I originally proposed

I originally called this "scene-based GMs" — multiple separate GMs
handing off. The framework's actual pattern is *one* GM that knows about
scenes (the `dialogic_and_dramaturgic__GameMaster` prefab). It takes a
`scenes` parameter — a sequence of `SceneSpec` — and runs them in order
via a `SceneTracker` component. Cleaner; uses what Concordia already
provides.

## How the scene mechanism actually works

After reading the prefab and the `scene_tracker` component, the actual
mechanism is mercifully simple — no LLM judgment is involved in the
transitions:

1. **`SceneTracker`** is a deterministic state machine. It counts rounds.
   After scene N's `num_rounds` are done, it advances to scene N+1.
2. **At each scene's first step**, `_maybe_queue_scene_start_premises`
   walks `scene.premise[entity_name]` for each participant and calls
   `entity.observe(text)` with each string. The strings become memory
   lines for that entity.
3. **`NextActionSpecFromSceneSpec`** reads the active scene's
   `action_spec.call_to_action` and uses *that string* as the question
   asked of whoever is acting that turn.
4. **`NextActingFromSceneSpec`** cycles through `scene.participants`
   deterministically — no LLM-based "who's next."
5. **`SceneBasedTerminator`** ends the sim when scenes run out.

So Alice doesn't "realize" anything. Her prompt changes between scene 1
and scene 2 in two specific ways: a new memory line, and a different
CTA. That's the whole knob.

## Moves

### Move 1 — Swap GM prefab

`dialogic__GameMaster` → `dialogic_and_dramaturgic__GameMaster`. Same
name (`conversation rules`), so the initializer's handoff still lands.

### Move 2 — Define 4 scenes

| # | Name | Rounds | CTA | Premise pressure |
|---|---|---|---|---|
| 1 | `small_talk` | 3 | "what does {name} say next?" | none |
| 2 | `the_recognition` | 2 | "does anything click? what does {name} say next?" | Alice: "now certain — same hair, same accent, same Bob. this is the moment to bring it up." / Bob: "something has been nagging at him — vague sense he's met her before." |
| 3 | `the_reckoning` | 4 | "defensively, honestly, or somewhere in between?" | Alice: "first instinct is to blame him, but also remembers her own sharpness." / Bob: "first instinct is to defend himself, but also remembers how checked-out he was." |
| 4 | `second_chance` | 2 | "reflecting on the coincidence of ending up at the same table tonight, what does {name} say?" | Both: "unexpectedly honest place. quietly wondering whether tonight means anything." |

Total: 11 rounds (well within `MAX_STEPS=20`).

### Move 3 — No code changes to goals or memories

Carried over from Experiment 01.

## What we did NOT change

- Asymmetric memories (Alice vivid, Bob hazy) — unchanged from 01
- Goals — unchanged from 01
- Initializer GM — unchanged
- Provider / model — OpenRouter + `anthropic/claude-sonnet-4.6`
- `MAX_STEPS=20`

## Premise style choice

I went with **internal pressure** ("Alice decides this is the moment")
rather than **external situational** ("a nearby table erupts about
Tinder"). Internal is more reliable for hitting beats but riskier in
that it can read on-the-nose if the model surfaces the premise text
verbatim. If the result feels too narrated, the right next experiment
is to rewrite the premises as external situational cues.

## What to watch for

1. **Does Alice actually reveal in scene 2?** And does it feel natural,
   or does she awkwardly recite the premise text?
2. **Does Bob's fumbling-toward-recognition land**, or does he go from
   total ignorance straight to full memory?
3. **Does the reckoning have any heat to it**, or do they jump to
   mutual admission too easily?
4. **Does the second-chance scene feel earned**, or like a forced
   coda?
5. **Are the premise strings audible in the dialogue?** If Alice
   literally says something like "this is the moment to bring it up"
   we've over-cued.

## Skepticism flag

I'm not confident this is enough. The model still has full creative
freedom; it could read "does anything click?" as a vague invitation and
just keep being polite. Even with a memory line literally saying *"this
is the moment,"* Sonnet 4.6 has been trained to be careful. If this
run still hedges, the next move is probably either (a) much blunter
premise text, or (b) the heavier hammers we keep in reserve —
mid-sim memory injection and chained goals.

## Post-run notes

(Fill in after running.)
