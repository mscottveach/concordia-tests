# Concordia Framework Notes

A running notebook of how Concordia actually works, written as I learn it.
Not a reference manual — a study guide to re-read when coming back cold.

## The three setup objects

Every sim wires up the same three things before calling `Simulation(...)`:

```python
model    = shared.make_model(...)     # the reasoning brain
embedder = shared.make_embedder()     # the memory-retrieval substrate
config   = build_config()             # the cast, stage, and turn budget
```

- **`model`** — a Concordia `LanguageModel`. Wraps Anthropic / OpenRouter / etc.
  Every "decision" in a sim is ultimately a call into this.
- **`embedder`** — `(text) -> ndarray`. Turns text into a vector. Used by
  *AssociativeMemory*: every observation/event gets stored both as text *and*
  as an embedding, so agents can recall semantically relevant memories
  (not just keyword matches). Runs locally via `sentence-transformers`
  (`all-MiniLM-L6-v2`) — no API call, no key.
- **`config`** — a `prefab_lib.Config` containing:
  - `prefabs`: the *catalog* of entity/GM types available to instantiate
  - `instances`: which prefabs to actually instantiate, with which params
  - `default_premise`: the opening scene
  - `default_max_steps`: turn budget

`config` is *what the world contains*. The *doing* happens in `sim.play()`.


ENTITES are collection of COMPONENTS.
COMPONENTS are called by an entity on a turn one by one and return strings that are cocnactenated and beceom the prompt that the entity sensd so the model.


## Prefab vs Entity

- **Prefab** = blueprint. A dataclass with default params and a `build()`
  method that constructs an entity.
- **Entity** = instance of a prefab. The actual running agent with memory and
  components wired up.


One prefab can produce many entities (Alice and Bob both come from
`basic__Entity`, with different `name` and `goal` params).

## Components

A **component** is a named module attached to an entity. Each component
has a `pre_act()` method that returns a piece of text.

When the entity is asked to act, the framework calls `pre_act()` on every
component in order and **stitches the results together into the LLM prompt**.

So:
- An entity *is* its component stack.
- The prompt an entity sends to the LLM is literally the concatenated
  `pre_act()` outputs.
- Different component stack → different prompt → different behavior.

Some components also hold state (memory, plan) and update it after each turn.

### Two kinds of components: context vs act

Every entity has:
- **Many context components** — they each have `pre_act()` returning text.
  The LEGO bricks that contribute to the prompt.
- **Exactly one act component** — the entry point and orchestrator. It
  gathers all the context components' `pre_act()` outputs and decides what
  to do with them.

Common act components:
- **`ConcatActComponent`** — used by regular entities like
  `basic__Entity` (see `basic.py:188`). Concatenates context outputs in
  order, asks the LLM what the entity does. Single-purpose.
- **`SwitchAct`** — used by GMs (see `dialogic.py`). Dispatches based on
  request type (next_actor, resolve, make_observation, terminate, etc.).

Act component lifecycle per request (one pass, not a loop):
1. Engine calls the act component — the only door in.
2. It gathers `pre_act()` from every context component.
3. It decides what to do with them.
4. Returns the action. Done until the next call.

Mental model: context components = the entity's organs. Act component =
the entity's executive function.

### How the prompt is stitched together

In `SwitchAct._context_for_action()`:
- Walk components in `component_order`
- Take each one's `pre_act()` output
- Skip empties
- Join with `\n`
- Collapse triple newlines to double (cosmetic cleanup)
- Components not in the order get appended sorted alphabetically

So the literal stitching is **ordered concatenation with newlines**.

But `SwitchAct` adds a second layer of orchestration on top: it dispatches
to different methods (`_next_acting`, `_resolve`, `_make_observation`,
`_next_game_master`, `_terminate`, etc.) based on the *type* of request.
Each method:
- Concatenates the same context (background priming for the LLM)
- BUT designates **one** component as the *answerer* — that component's
  `pre_act()` output IS the result
- If no designated answerer exists, falls back to an `InteractiveDocument`
  chain-of-thought that asks the LLM directly (the "YOLO case" in the code)

So a component's `pre_act()` text can play two very different roles
depending on which method it's serving:
- **As background:** concatenated into the prompt as priming.
- **As the answer:** returned verbatim as the GM's decision.

### `basic__Entity` vs `basic_with_plan__Entity`

Same LLM, same goal text, but different component stack:

`basic__Entity`:
- Instructions, Observation, SituationPerception, SelfPerception,
  PersonBySituation, Goal (optional), Memory

`basic_with_plan__Entity` adds:
- **RelevantMemories** — actively retrieves memories similar to the current
  situation and injects them into the prompt
- **Plan** — maintains an explicit, persistent plan the agent updates each
  turn

Result: `basic` is reactive turn-by-turn; `basic_with_plan` carries a
plan forward and is closer to a goal-directed agent.

## The Game Master and the turn loop

The GM is also an entity — built from components, wrapped in
`EntityAgentWithLogging`. It's not hand-coded behavior, it's a composition
of LLM calls.

For `dialogic__GameMaster` (see
`concordia/prefabs/game_master/dialogic.py`), the component stack includes:

| Component | Role |
|-----------|------|
| `instructions` | static "you are a GM" text |
| `player_characters` | "the players are: Alice, Bob" |
| `repetitive_conversations_end` | "end if repetitive" rule (constant text) |
| `relevant_memories` | top-N memories similar to current events |
| `observation` / `display_events` | recent observations & event history |
| `memory_component` | the AssociativeMemory bank |
| `next_actor` | picks who speaks next |
| `next_action_spec` | what kind of action is expected (speech) |
| `event_resolution` | turns a raw action into a narrated event |
| `make_observation` | writes what each entity perceives |
| `send_events_to_players` | routes events to entities who saw them |
| `next_game_master` | decides "is this conversation over?" |

The outer simulation loop (`prefabs/simulation/generic.py`) asks the GM
these questions in sequence, **each one a separate LLM call**:

1. **Who acts next?** → `next_actor` builds a prompt and asks the model.
   - `acting_order='fixed'` → round-robin (no LLM call)
   - `'random'` → random pick (no LLM call)
   - `'game_master_choice'` (default) → LLM picks
2. **What kind of action?** → `next_action_spec` (here, fixed to speech).
3. **Active entity, what do you do?** → The chosen entity (Alice or Bob)
   runs *its own* component stack, builds *its own* prompt, and produces
   free-text action.
4. **What actually happens?** → `event_resolution` runs the action through
   resolution steps. In `dialogic` this is basically pass-through. A
   physically-situated GM would ask "is this possible? what's the outcome?"
5. **Who sees it?** → `send_events_to_players` routes the event.
6. **What does each witness perceive?** → `make_observation` writes the
   observation text for each player; `observation_to_memory` stores it.
7. **Is the conversation over?** → `next_game_master` asks the model.
   Yes → hand off to `next_game_master_name`. No → loop.

Then the outer loop checks `max_steps` and goes again.

## What entities know (and when they learn it)

Entities start *almost blind*. When `build()` returns an entity, all it
has is:

- Its own name (from `params`)
- Its own goal (from `params`, if any)
- Static text from its components (e.g. `Instructions`)
- An empty memory bank

It does **not** know the premise, who else exists, or what setting it's
in. All world knowledge flows in through observations the GM sends each
turn.

### How the premise actually reaches entities

From `sequential.py:244-246`:

```python
if premise:
    premise = f'{EVENT_TAG} {premise}'
    game_master.observe(premise)
```

The premise is observed by the **GM only**. The GM then composes
per-entity observations (Alice may see something different from Bob —
only what they would perceive).

### The pattern

**The GM holds world state. Entities are blind unless told.**

- The GM has its own memory bank and observes the premise at step 0.
- Each entity has its own memory bank, starts empty.
- All world-knowledge flow into entities goes through:
  `GM → make_observation → entity.observe → entity memory`
- If the GM decides Alice doesn't see something, Alice never knows.

### Seeding entities with backstory: the INITIALIZER role

If you want entities to know who they are beyond just a name and goal —
backstory, relationships, prior history — use an **initializer GM**.

It's opt-in. The `Role` enum (`concordia/typing/prefab.py:28-31`) has
three values: `ENTITY`, `GAME_MASTER`, `INITIALIZER`. To add one,
include an `InstanceConfig(role=Role.INITIALIZER, ...)` in your
`instances` list. The runner sorts initializers ahead of regular GMs
and runs them first.

An initializer typically uses an action spec with
`OutputType.SKIP_THIS_STEP` — no entity acts during the init pass. Its
only job is to generate rich observations like *"you are Alice, a
35-year-old barista from Manchester..."* and inject them into each
entity's memory before the real sim starts.

`sim_pub.py` has **no** initializer, so Alice and Bob start truly empty
— they don't even know the other exists until the first dialogic GM
observation tells them.

### The full step-by-step flow

1. Engine picks the active GM (may switch GMs via `next_game_master`).
2. **For every entity**, the engine asks the GM to compose an
   observation and sends it to that entity via `entity.observe`. This is
   how entities learn what just happened / what they perceive this step.
3. Engine asks the GM `next_acting` → which entity acts now, and what
   kind of action.
4. If action type is `SKIP_THIS_STEP`, skip the action phase (initializer
   pattern).
5. Otherwise: engine calls `next_entity.act(spec)` → entity returns
   free-text action using its own component stack.
6. Engine sends the action back via `resolve()` → the GM produces a
   narrated event, which becomes part of the GM's memory (and feeds the
   next step's observations to entities).
7. Engine asks the GM `terminate` → done? If yes, stop. If no, increment
   step and loop.

## Memory: where it lives, how it flows

### What memory actually is

`AssociativeMemoryBank` is the storage primitive (see
`concordia/associative_memory/basic_associative_memory.py`). Internally:

```python
self._memory_bank = pd.DataFrame(columns=['text', 'embedding'])
```

So at the bottom, **memory is a pandas DataFrame** — two columns, the raw
text of an observation and its vector embedding. Lives in RAM in a Python
object for the lifetime of the `Simulation`. No database, no file, no
global store.

Every `bank.add(text)` embeds the text and appends a row. Every
`bank.retrieve(query, k=10)` embeds the query, runs cosine similarity
against every row, and returns the top-K matches.

### Who creates banks (and when)

The `Simulation` constructor creates them automatically. Two kinds:

1. **One shared GM memory bank** (`generic.py:93`):
   ```python
   self.game_master_memory_bank = AssociativeMemoryBank(
       sentence_embedder=embedder, allow_duplicates=True)
   ```
   *All* GMs (initializer, dialogic, any others) share this single bank.
   That's how GMs hand off to each other and still see the same world.

2. **One memory bank per entity** (`generic.py:195`, in `add_entity`):
   ```python
   memory_bank = AssociativeMemoryBank(sentence_embedder=self._embedder)
   entity = entity_prefab.build(model=..., memory_bank=memory_bank)
   ```
   Each entity gets its own private bank. Alice's memory and Bob's memory
   are completely isolated — different Python objects.

So you don't "reserve" memory. The Simulation constructor instantiates
banks while processing your `instances` list.

### How banks flow into entities

Single channel: the prefab's `build()` method.

```
Simulation.__init__()
  → creates memory_bank
  → calls entity_prefab.build(model=..., memory_bank=memory_bank)
       → wraps it in an AssociativeMemory *component*
       → component goes into the entity's context_components dict
  → entity now owns its component, which owns its bank
```

The `AssociativeMemory` component (in `actor_components.memory`) is a
thin wrapper that exposes the bank to the rest of the entity. Other
components that need to read or write memory don't touch the bank
directly — they look up the `AssociativeMemory` component by key and
call methods on it.

### How memory gets written to and read from

**Writes** happen via `entity.observe(text)`:

1. The act component receives the observation.
2. The `ObservationToMemory` context component picks it up.
3. It calls into the `AssociativeMemory` component → `bank.add(text)` →
   DataFrame row appended (with embedding).

**Reads** happen via retrieval components like `AllSimilarMemories`
(see `dialogic.py:111`):

1. The component builds a query string (often summarizing the current
   situation).
2. Calls into the `AssociativeMemory` component → `bank.retrieve(query,
   k=10)`.
3. Top-K matching memories come back as text, get formatted, and become
   that component's `pre_act()` output — which gets concatenated into the
   next LLM prompt.

### Subtler facts

- **Memory is thread-safe.** The bank has a lock around all reads/writes
  (`_memory_bank_lock`). Async engines can call concurrently.
- **Memory is checkpointable.** `get_state()` serializes the DataFrame to
  JSON. `Simulation.make_checkpoint_data()` walks every entity and saves
  each bank.
- **GMs share, entities don't.** This asymmetry is intentional: the
  world is "real" (one truth, the GM bank); each agent has its own
  private subjective experience.

## Building a custom simulation

When writing a new sim on top of this framework, you'll typically create:

- **Custom components** — the main customization point. Anything the
  framework doesn't already do (track a relationship score, maintain an
  inventory, encode emotional state, custom resolution rules) becomes a
  new component.
- **The sim file itself** — premise, `build_config()`, `InstanceConfig`s,
  `main()`. Always.
- **Custom prefabs** — only when you want to *bake in* a specific reusable
  component stack. For one-off sims, just instantiate existing prefabs
  with different params (like `sim_pub.py` does).

What you usually *don't* write:
- Act components (`ConcatActComponent` and `SwitchAct` cover almost
  everything)
- Memory infrastructure
- The simulation runner

Typical custom sim = **one sim file + a handful of custom components**,
with prefabs reserved for when you need them.

## Mental model summary

- `model` = brain. `embedder` = recall. `config` = world.
- Prefab = blueprint. Entity = instance.
- An entity = many context components + one act component.
- Context components produce text. The act component decides what to do
  with it.
- The GM is just another entity, but with components that produce flow
  decisions (who acts, what happens, is it over).
- Every "decision" in a sim is an LLM call shaped by a component stack.

## Open questions / to explore next

- How does `AssociativeMemory` decide what counts as "similar enough" to
  retrieve? Threshold? Top-K?
- How does `event_resolution` get more interesting in non-dialogic GMs
  (e.g. `situated.py`)?
- When does an entity update its `Plan` (in `basic_with_plan`)?
- What's the actual signature/interface a custom component needs to
  implement? Base class? Required methods?

## Q&A

The same material as above, but indexed by the questions I actually asked
while learning the framework. Repetitive with the structured sections on
purpose — different access pattern.

### What parts does writing a simulation customize with this framework?

Three layers, in order of how often you'll touch them:

1. **The sim file itself** (always). Premise, `build_config()`,
   `InstanceConfig`s, `main()`. This is where you declare *what world*
   you're simulating and *who's in it*.
2. **Custom components** (the main customization point). Anything the
   framework doesn't already do — tracking a relationship score,
   maintaining an inventory, encoding emotional state, custom resolution
   rules — becomes a new component you write.
3. **Custom prefabs** (occasional). Only when you want to *bake in* a
   specific reusable component stack you'll spin up across many sims. For
   one-off sims, just instantiate existing prefabs with different params,
   the way `sim_pub.py` does.

What you usually *don't* write: act components (`ConcatActComponent` and
`SwitchAct` cover almost everything), memory infrastructure, the
simulation runner.

Typical custom sim = **one sim file + a handful of custom components**,
with prefabs reserved for when you need them.

### Are act components the thing that manages the loop for an entity over its other components?

Close, but I'd sharpen it slightly. The act component isn't really a
*loop* — it's the **entry point and orchestrator for a single action
request**.

When something external (the simulation engine, or another entity) asks
the entity to act, the flow is:

1. Engine calls the act component — that's the only door in.
2. Act component gathers `pre_act()` outputs from every context component
   (one pass, not a loop in the iterative sense).
3. Act component decides what to do with them — for `ConcatActComponent`,
   that's "concatenate in order and ask the LLM what to do." For
   `SwitchAct`, that's "dispatch based on request type, treat one
   component as the answerer."
4. Act component returns the resulting action.

Then it's done until the next request comes in.

A cleaner framing:

- **Context components** = the entity's organs (memory, perception, plan).
  They produce text on demand.
- **Act component** = the entity's executive function. It collects the
  organs' contributions and decides how to respond.

The "loop" you might be thinking of is the *outer simulation loop* that
keeps calling entities and the GM round after round. The act component is
just what wakes up each time the engine knocks.

### What's the high-level flow of control? What do entities know up front, and when do they learn about the world?

Entities start *almost blind*. When `build()` returns an entity, it has
only:

- Its own name and goal (from `params`)
- Static text from its components (e.g. `Instructions`)
- An empty memory bank

It does **not** know the premise, who else exists, or what setting it's
in.

**The premise is observed by the GM only**, not the entities. From
`sequential.py:244-246`:

```python
if premise:
    premise = f'{EVENT_TAG} {premise}'
    game_master.observe(premise)
```

The pattern: **the GM holds world state; entities are blind unless told.**
All world-knowledge flow into entities goes through
`GM → make_observation → entity.observe → entity memory`. If the GM
decides Alice doesn't see something, Alice never knows.

**To seed entities with backstory** (who they are, prior history), use an
*initializer GM*. It's opt-in — the `Role` enum has `ENTITY`,
`GAME_MASTER`, and `INITIALIZER`. You add one via
`InstanceConfig(role=Role.INITIALIZER, ...)`; the runner sorts them
ahead of regular GMs. Initializers typically use `SKIP_THIS_STEP` action
specs so no entity acts during init — their only job is to push rich
"who you are" observations into each entity's memory.

`sim_pub.py` has no initializer, so Alice and Bob start empty and only
learn about the pub, the rainy evening, and each other from the
dialogic GM's first round of observations.

**The full step-by-step flow:**

1. Engine picks the active GM (may switch via `next_game_master`).
2. For every entity, engine asks the GM to compose an observation, then
   sends it to that entity via `entity.observe`. This is when entities
   learn what just happened.
3. Engine asks the GM `next_acting` → which entity acts now + what kind
   of action.
4. If action type is `SKIP_THIS_STEP`, skip the action phase (initializer
   pattern).
5. Otherwise: engine calls `next_entity.act(spec)` → entity returns
   free-text action via its own component stack.
6. Engine sends the action to the GM via `resolve()` → GM produces a
   narrated event, which becomes part of GM memory (and feeds next
   step's observations).
7. Engine asks the GM `terminate` → done? If yes, stop. If no, increment
   step and loop.

### How does memory work? Where is it held, who reserves it, and how does it get passed around?

At the bottom, memory is a **pandas DataFrame** with two columns
(`text`, `embedding`) wrapped in an `AssociativeMemoryBank` object,
sitting in RAM for the lifetime of the `Simulation`. Not a database,
not a file.

**Who creates banks (and when):** the `Simulation` constructor,
automatically. Two kinds:

- **One shared GM memory bank** for all GMs (initializer, dialogic,
  etc.) — that's how they hand off and still see the same world.
- **One private bank per entity** — Alice and Bob have completely
  isolated memory; different Python objects, different DataFrames.

You don't reserve memory. Adding an `InstanceConfig` to your `instances`
list causes the Simulation to instantiate a fresh bank for that
entity/GM during `add_entity` / `add_game_master`.

**How banks get to entities (one channel only):** the prefab's
`build(memory_bank=...)` call. Inside `build()`, the bank gets wrapped
in an `AssociativeMemory` *component* and added to the entity's
context_components dict. From that point on, the entity owns its
component, the component owns its bank, and nothing else passes it
around.

**Writes** flow via `entity.observe(text)` → the `ObservationToMemory`
component → `AssociativeMemory.add()` → `bank.add()` → embed + append
DataFrame row.

**Reads** flow via retrieval components like `AllSimilarMemories` →
build a query → `bank.retrieve(query, k=10)` → top-K matches by cosine
similarity → text becomes part of `pre_act()` output → concatenated
into the next LLM prompt.

**Subtler facts:**

- The bank is **thread-safe** (lock around reads/writes).
- It's **checkpointable** — `get_state()` serializes the DataFrame to
  JSON.
- **GMs share one bank; entities each have their own.** Intentional
  asymmetry: the world is "real" (one truth, the GM bank); each agent
  has its own private subjective experience.

| Question | Answer |
|---|---|
| Who reserves it? | The `Simulation` constructor, automatically. |
| Where is it held? | A pandas DataFrame in an `AssociativeMemoryBank` object, in RAM. |
| Is it a variable? | Yes — an attribute on the entity's `AssociativeMemory` component. |
| How does it get passed around? | Once, at build time, via `entity_prefab.build(memory_bank=...)`. After that the entity owns it. |
