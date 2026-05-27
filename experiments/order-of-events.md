# Order of Events

## Where do I put my creative input?

Most creative work lands in one of four places:

1. **What everyone in the world knows** — facts about the setting, time, place, atmosphere.
2. **What each character knows about themselves and their history** — bios, prior events, relationships.
3. **What each character wants right now** — their goal.
4. **Beat-by-beat narrative pressure** — what changes per scene, the question being asked of the characters.

Everything else (component wiring, GM choice, model selection, max_steps, etc.) is plumbing.

### Details — where exactly each one lives

- **World facts (`shared_memories`)** — list of strings; every agent receives each string as an observation at the start. Lives in the **initializer GM's `params`** in `sim_pub.py`.
- **Per-character knowledge (`player_specific_memories`)** — dict of `{agent_name: [strings]}`; each string becomes a separate memory for that agent. Lives in the **initializer GM's `params`**.
- **Per-character goal (`goal`)** — a single string the Goal component contributes to every prompt that agent generates. Lives in **each agent's `params`** in their `InstanceConfig`.
- **Opening premise (`premise`)** — a single string describing the scene start. Passed to **`sim.play(premise=...)`** in `main()`. Currently held in the `PREMISE` constant.
- **Per-scene narrative pressure (`scene.premise`)** — dict of `{agent_name: [strings]}` injected into each agent's observation queue at the start of that scene. Lives in **each `SceneSpec`** inside `build_scenes()`.
- **Per-scene question (`scene.action_spec.call_to_action`)** — the question entities are asked while this scene is active. Lives in **each `SceneSpec`** inside `build_scenes()`.

### Optional / situational

- **`player_specific_context`** — prose seed used by the LLM to invent childhood memories. Only consumed when childhood generation is enabled. Lives in the initializer GM's `params`.
- **Custom components** — wire EmotionalStance or any other component into the GM via `extra_components` in the sim GM's `params`. (Agents don't expose this — would require a custom prefab.)

## Entities

We start with entities. There are two types:

- **Agents** — the characters who act in the scene (e.g. Alice, Bob).
- **Game Masters (GMs)** — the orchestrators that decide what happens. Concordia ships several types, but a typical setup has two:
  - an **initializer GM** — is the active for the first iteration of the control loop; it sets the stage and seed each agent's memory
  - a **sim GM** — runs the actual scene from there onward (e.g. the dialogic or dramaturgic GM)

## Seed initializer GM with the following information:

The initializer's job is to give the agents their starting memories (which may or may not include childhood).

  - It has a list of shared_memories which it passes to every agent and itself (via the controller) through "observe." Each string in the list becomes one observation that every agent receives.

    ```
    shared_memories = [
      "It is a Tuesday evening in late October. A steady rain has been falling for hours.",
      "We are inside The Lamb and Flag, a small pub tucked down a side street in Covent Garden, London.",
      "The pub is crowded tonight — everyone driven inside by the weather.",
    ]
    ```

  - It has a dict of player_specific_memories which it passes to the players through "observe." Keys are agents and values are lists of strings where each string is a memory to be given to the agent.

    ```
    player_specific_memories = {
      "Alice": [
          "Alice is a 32-year-old PhD student...",
          "A year ago Alice went on a Tinder date...",
          "Alice's best friend Maria moved to Berlin last year",
      ],
      "Bob": [
          "Bob is a 45-year-old graphic designer...",
          "Bob's dog died two months ago",
      ]}
    ```
  - It also has a dict of player_specific_context. Keys are agents and values are single prose strings describing that agent's life context. It is only used to generate childhood memories — if childhood generation is turned off, this dict is never read.

    ```
    player_specific_context = {
      "Alice": "Alice is a 32-year-old PhD student in linguistics, recently moved to London from Toronto. She is the kind of person who pays close attention to others.",
      "Bob": "Bob is a 45-year-old freelance graphic designer who grew up in London, currently in the middle of a rough patch at work.",
    }
    ```

  - The premise (passed to `sim.play()`, not as an initializer param) is pushed to `game_master[0]` (which is probably the initializer GM) via its `observe()` method before the loop starts. All GMs share a single memory bank, so once the initializer's `ObservationToMemory` stores the premise, every other GM can retrieve it from shared memory. Only the initializer has it in its own `LastNObservations` rolling window though.

    ```
    sim.play(premise="Alice and Bob are strangers who happen to share a small table at a crowded London pub on a rainy evening.")
    ```

## The Control Loop

We will use engine and controller both to mean the surrounding code that controls the execution flow. It runs the iteration loop and acts as the orchestrator: each step it asks the active GM a sequence of questions via `game_master.act()` (should we terminate, who's the next active GM, what does each entity observe, who acts next, what action type, how to resolve the proposed action), and routes returned text back out to the agents via `entity.observe()`. It never touches queues or memory directly — those live inside the GMs' and agents' own components. Its job is purely flow control and routing.

0. **Before the loop starts:** if a `premise` was passed to `sim.play()`, the engine calls `observe(premise)` on the initializer GM. This triggers the initializer's observation-handling components to fire — `ObservationToMemory` writes the premise into the GM's memory bank, and `LastNObservations` adds it to the recent-observations rolling window.

1. Controller asks the active GM whether the sim should terminate. The GM answers in one of two ways:

   - **Deterministic function** — runs custom logic (e.g. a scene tracker, an iteration counter, a flag) and returns yes/no without calling the model.
   - **Ask the language model** — builds a prompt and asks the model whether the conversation/simulation is over.

2. Controller asks the currently-active GM which GM should run this step. The GM returns a GM name — either its own (no handoff) or a different one (handoff to that GM).

   - **Note:** this is the phase where the initializer GM does its memory-seeding work. On its first call, it seeds the queues and returns its OWN name — so it stays active for that whole iteration. The handoff to the sim GM only happens on the NEXT iteration's call to this same phase.

3. For each entity in the sim, the controller asks the active GM to produce an observation for that entity. The GM drains that entity's observation queue, returns the text up to the controller, and the controller then calls `entity.observe(text)` on the agent. The `text` here is the concatenation of all observations that were queued for that entity this step, joined into a single string.

   - If the queue for an entity is empty, the GM either calls the model to generate an observation as a fallback, or (if `allow_llm_fallback=False`) skips that entity for the step.

   - When the LLM fallback fires, the prompt sent to the model contains:
     - The pre_act outputs of the GM's configured context components (in our dramaturgic GM: `LastNObservations` for recent observation history, and `DisplayEvents` for recent resolved events).
     - A meta-statement: `Working out the answer to: "<action_spec.call_to_action>"`.
     - The actual question: `What does {entity_name} observe now? Never repeat information that was already provided to {entity_name} unless absolutely necessary. Keep the story moving forward.`

4. Controller calls `gm.act(action_spec)` with `output_type=NEXT_ACTING` to find out who acts next. The flow inside:

   - GM calls `pre_act` on every context component in parallel; each guards on the action_spec and returns either an empty string or its info.
   - GM collects all results into a contexts dict.
   - GM hands the contexts dict to its act component, `SwitchAct`.
   - `SwitchAct` sees `output_type=NEXT_ACTING` and dispatches to its `_next_acting` method.
   - `_next_acting` looks up the value at the `next_acting` key in the contexts dict — that value is the pre_act output of whatever component is registered there (in our setup, `NextActingFromSceneSpec`).
   - The value (an entity name) bubbles back up to the controller.

5. Controller calls `gm.act(action_spec)` again, this time with `output_type=NEXT_ACTION_SPEC`, to find out what kind of action the chosen entity is being asked to take. The entity name from step 4 gets baked into the prompt as a string via `.format(name=next_object_name)` — the GM never sees the entity object itself.

   - The internal flow is the same as step 4: pre_act on every component, contexts dict, SwitchAct dispatches (this time to `_next_entity_action_spec`), looks up the value at the next_action_spec key (in our setup that's `NextActionSpecFromSceneSpec`, which returns the active scene's action_spec).
   - The returned value bubbles back up to the controller, which parses it into an `ActionSpec` object.
   - Controller validates the name from step 4 against its `entities_by_name` dict — if the GM returned a name that isn't a real entity, it raises an error (guards against the LLM hallucinating an invalid name).
   - Controller does a dict lookup to get the actual entity object, and now has the tuple `(entity_object, action_spec)` as the combined result of steps 4 and 5.
   - If `action_spec.output_type == SKIP_THIS_STEP`, the controller skips the rest of this iteration (no entity acts, no resolve) and `continue`s to the next iteration. This is the path the initializer takes on its iteration.

6. In a conversational setup like ours, `action_spec.output_type` is usually `FREE` — the entity will be asked an open-ended question and respond with free-form text. The controller now calls `entity.act(action_spec)` on the chosen entity.

   - The entity (e.g. Alice) calls `pre_act` on every context component in parallel — `Goal`, `Instructions`, `SelfPerception`, `SituationPerception`, `PersonBySituation`, etc.
   - The entity collects all the pre_act outputs into a contexts dict.
   - The entity hands the contexts dict to its act component, `ConcatActComponent`.
   - Unlike the GM's `SwitchAct`, `ConcatActComponent` doesn't dispatch by output_type. It concatenates all the context outputs in the configured order, appends the action_spec's `call_to_action` as the question, and sends the full assembled prompt to the LLM as one call.
   - The LLM's response is the entity's action text.
   - That text bubbles back up to the controller.

7. Controller takes the action text and runs the **resolve phase** — three calls to the GM in sequence:

   - First, normalizes the format: if the action doesn't already start with the entity's name, prefix it (so it becomes `"Alice: <her dialogue>"`).
   - **Call 1: `gm.observe(putative_event)`** — pushes the proposed action into the GM as an observation, tagged `[putative_event]`. The GM's components (`ObservationToMemory`, `LastNObservations`, etc.) react to it.
   - **Call 2: `gm.act(action_spec)` with `output_type=RESOLVE`** — asks the GM to resolve the proposed event into the actual event. Same dispatch machinery as before: pre_act on all components, contexts dict to SwitchAct, SwitchAct dispatches to `_resolve`, which reads the value at the resolve key. In our dialogic_and_dramaturgic GM the resolve is essentially pass-through (the putative event becomes the event verbatim). A richer GM (situated, game-theoretic) might modify the action — e.g. "Alice tries to stand but the pub is too crowded; she sits back down."
   - **Call 3: `gm.observe(resolved_event)`** — pushes the final event back into the GM, tagged `[event]`. This is what officially gets recorded.
   - During Call 2, the GM's `SendEventToRelevantPlayers` component runs as part of pre_act and queues the resolved event into the observation queues of all entities who would have witnessed it — to be delivered in the NEXT iteration's step 3.

After step 7, the iteration ends. The controller increments the step counter and the loop starts over at step 1.

## How do I...?

### How do I trigger an event to happen based on unfolding events?

*Example: make a character called The Devil appear only when one of the characters says "the devil."*

You need two pieces: a **watcher** that detects the trigger condition, and an **injector** that pushes the response into the sim. Two cleanest implementation paths, in order of how local they feel:

**Option 1 — Custom thought chain in `event_resolution_steps`.**

Add a step to the GM's resolve pipeline. It runs every time an event is being resolved, inspects the candidate event for the trigger keyword, and modifies the event to include the response if it's found.

```python
def maybe_summon_the_devil(chain_of_thought, candidate_event, active_player_name):
    if "the devil" in candidate_event.lower():
        return (
            candidate_event
            + " At that moment, a man in a red suit steps out of "
            + "the shadows of the next booth."
        )
    return candidate_event
```

Plug it into the GM's `event_resolution_steps` list. From the next iteration onward, any agent who witnessed the event will see the modified version (since the resolved event is what gets queued for them).

This is the simplest path. Fires synchronously with the resolution itself. No new components, no extra plumbing.

**Option 2 — Custom component on the GM that watches observations.**

Attach a component to the GM whose `pre_observe` hook watches incoming text for the trigger. When it sees one, it calls `MakeObservation.add_to_queue(player_name, devil_appearance_text)` for each player. Next iteration's observation phase delivers the appearance to them.

```python
class WatchForTheDevil(SomeBaseComponent):
    def pre_observe(self, text):
        if "the devil" in text.lower():
            make_obs = self.get_entity().get_component("__make_observation__")
            for name in self._player_names:
                make_obs.add_to_queue(
                    name,
                    "A man in a red suit steps out of the shadows.",
                )
```

This decouples the trigger from the resolution phase — useful if the trigger should fire on observations OTHER than the latest event (e.g., things the GM has noticed but haven't been "resolved").

**Caveat: narrative appearance vs. actual entity.**

If The Devil only needs to *appear* in the narrative — described in observations, witnessed by the characters, but never actually takes his own turn — both options above are sufficient. The Devil exists as text in everyone's memory.

If The Devil needs to be a **real entity** that can be picked by `next_acting` and given an `act()` call to produce his own dialogue, you'd need to either:
- Pre-configure The Devil as an inactive entity at sim startup and have your trigger flip a flag that adds him to the active participants list, OR
- Modify the framework to support truly dynamic entity addition (non-trivial).

For most narrative purposes, the text-only appearance via Option 1 or 2 is enough.

## Walkthrough: building sim_devil

A concrete worked example. The sim: hotshot lawyer **Jordan** negotiates with **Mr. Scratch** (the devil) over a soul contract Jordan asked time to review. The twist: Jordan brings the contract back heavily marked up and plans to wear Mr. Scratch down before revealing what he actually wants. Below: each creative-input step, what we wrote, and where exactly in `sim_devil.py` it lives.

### Step 1 — Premise

The one-paragraph opening situation. Observed by the initializer GM (not the agents directly).

**Where it lives:** the `PREMISE` constant near the top of `sim_devil.py`, passed via `default_premise=PREMISE` inside `build_config()`.

```python
PREMISE = (
    "Mr. Scratch — the devil — has manifested in Jordan's law office, "
    "returning to collect the final signature on a soul contract Jordan "
    "asked for time to review. He expects a quick formality. Jordan "
    "reaches for the contract: it's covered in red marks, cross-outs, "
    "and annotations."
)
```

### Step 2 — Shared memories

World/setting facts both characters know. Each string is queued as one observation for every agent at sim start.

**Where it lives:** the initializer GM's `InstanceConfig.params["shared_memories"]`.

```python
"shared_memories": [
    "It is late afternoon. We are in Jordan's law office on the 34th floor...",
    "On the desk between us sits the contract — pages of dense legal text...",
    "This is the second meeting. Mr. Scratch presented the contract some days ago...",
    "The deal: Mr. Scratch grants Jordan whatever was originally agreed; in exchange, Jordan signs over his soul.",
]
```

### Step 3 — Jordan's bio + memories

Per-character knowledge for Jordan. Three entries: identity & record, what his preparation produced, his stance toward Mr. Scratch.

**Where it lives:** the initializer GM's `InstanceConfig.params["player_specific_memories"]["Jordan"]`.

```python
"Jordan": [
    "Jordan is a 36-year-old attorney widely regarded as the sharpest negotiator alive...",
    "Jordan spent the past several days reading the contract line by line...",
    "Jordan does not view Mr. Scratch with awe, fear, or theological reverence...",
]
```

### Step 4 — Mr. Scratch's bio + memories

Per-character knowledge for Mr. Scratch. Four entries: identity, the routine he expects, the deferred-consideration hook (planted neutrally for later reveal), his current expectation.

**Where it lives:** the initializer GM's `InstanceConfig.params["player_specific_memories"]["Mr. Scratch"]`.

```python
"Mr. Scratch": [
    "Mr. Scratch is the devil. He has been making these deals for as long as souls have been bought and sold...",
    "The deal always goes the same way. The mortal is nervous, deferential...",
    "When he and Jordan first met, Jordan asked to defer the question of consideration...",
    "Today's meeting is purely administrative...",
]
```

### Step 5 — Jordan's goal

What Jordan is actively trying to do. Contributed verbatim to every prompt he generates, via his Goal component.

**Where it lives:** Jordan's `InstanceConfig.params["goal"]`.

```python
"goal": (
    "Jordan's plan is to wear Mr. Scratch down before getting to what "
    "he actually wants. He intends to work methodically through every "
    "red mark on the contract... He knows exactly what he wants. He "
    "is in no hurry to mention it."
),
```

### Step 6 — Mr. Scratch's goal

**Where it lives:** Mr. Scratch's `InstanceConfig.params["goal"]`.

```python
"goal": (
    "Mr. Scratch's goal is simple: close the deal, get the signature, "
    "and get out. This is routine... He intends to be polite but "
    "efficient and to be out of this office within minutes."
),
```

Deliberately set as a *confident-and-bored* starting state, not pre-irritated — the irritation is the destination, not the opening note.

### Step 7 — Scenes (deferred)

Left as a single placeholder scene running for `MAX_STEPS`. We're letting the model produce the arc naturally first, before adding scripted structure.

**Where it would live when we add it:** the `build_scenes()` function returns a list of `SceneSpec` objects. Each `SceneSpec` contains:
- `scene_type.name` — scene identifier
- `scene_type.action_spec.call_to_action` — the question asked of each entity during this scene
- `participants` — list of entity names
- `num_rounds` — how many rounds the scene lasts
- `premise` — `{entity_name: [strings]}` injected as observations at scene start

That list gets passed via the sim GM's `InstanceConfig.params["scenes"]`.






