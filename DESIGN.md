# Project Design Notes

A living record of design decisions for the concordia-tests project.
Updated as decisions are made, approaches change, or open questions
resolve. Not a spec — a memory aid for "what did we decide and why."

---

## Replay Dashboard

**Goal.** Watch a Concordia simulation play out clearly — see exactly
what happened each turn, what each entity knows at any given turn,
without wading through the echoes and putative/resolved/observed
repetition that fills the markdown logs. Optimized for the debugging-
plus-story-reading use case: "what happened, and why did they do that."

### Design

Two artifacts, decoupled. The contract between them is a structured
log file written by the sim and consumed by the dashboard.

```
   sim.play()  ──>  per-turn JSONL log file  ──>  dashboard app
```

Sim writes the log. Dashboard reads it. They never talk directly. The
log file is a portable artifact — saveable, shareable, replayable
without rerunning the (paid) simulation.

### Log format (JSONL)

**Design principle: store rich, query narrow.** The log captures the
*full* state we might ever want to investigate. The dashboard filters /
windows at display time. This way future-us can change what to surface
(more memory, different layers, new views) without having to rerun
the sim, which costs money and time.

One JSON object per line, one line per simulation step. Schema:

```json
{
  "turn": 7,
  "actor": "Quinn",
  "resolved_event": "Event: Quinn: Quinn presses the red button...",
  "putative_event": "Quinn: Quinn presses...",     // optional, for diff
  "entities": {
    "Quinn": {
      "all_observations": ["...", "...", "..."],   // EVERY obs delivered so far
      "all_actions": ["..."],                      // EVERY action taken so far
      "memory_size": 47                            // raw count for quick view
    },
    "Sam": {
      "all_observations": ["...", "..."],
      "all_actions": [],
      "memory_size": 23
    }
  },
  "queued_observations": {
    "Quinn": ["[PANEL] circle now glows red..."]    // queued THIS turn by components
  }
}
```

Captures per turn:
- the actor and what they did
- each entity's COMPLETE observation/action history through this turn
- any observations queued by components THIS TURN (delta, since they
  get folded into next turn's all_observations)

**On file size:** text compresses well. A ~25-turn sim with full
memory dumps is probably under 200KB uncompressed. Not a real
constraint. If we ever hit a constraint at very long sims (1000s of
turns), we can switch to event-sourcing format (log only deltas,
dashboard reconstructs state by replay) — but that's a future
optimization, not a starting point.

Reconstructable from `raw_log` + entity memory introspection.

### Dashboard

Streamlit app, single Python file, takes a log path as argument.

Layout (per the discussion sketch):

```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Quinn       │ │ Sam         │ │ GM          │
│ Recent obs  │ │ Recent obs  │ │ Last events │
│ Last action │ │ Last action │ │             │
└─────────────┘ └─────────────┘ └─────────────┘
┌─────────────────────────────────────────────┐
│ Event stream (turn N highlighted)           │
│ - turn 1: Quinn says "Hello?"               │
│ - turn 2: Sam says "Yeah, I can hear..."    │
│ - turn 7: Quinn presses red on circle  ◀── │
│ - ...                                       │
└─────────────────────────────────────────────┘
       [◀ prev]   [turn 7 / 25]   [next ▶]
```

Turn slider drives everything. Entity cards show that turn's state.
Event stream highlights the current turn but shows all events.

### Layers of detail (per discussion)

1. **Default** — last 8 observations + last action per entity, event
   stream. The "what's happening" feed.
2. **Expand** — full observation history. Forensic view.
3. **Deep-dive** — the actual LLM prompt for a chosen turn. Wall of
   text; only when "I can't tell from 2 what went wrong."

MVP ships layer 1 only. Layers 2 and 3 are v1.1.

### Why post-hoc / replay-only (not live)

Live polling adds complexity (concurrency, refresh, partial state)
for little gain over "open the log file in your dashboard." Logs as
portable artifacts also means we can debug a months-old run without
rerunning, share logs with future-self or others, and compare two runs
side-by-side. Live mode is something we can add later if we ever find
we actually need it — but most use cases are forensic.

### Implementation plan

1. **`shared.write_replay_log(sim, path)`** — extracts data from a
   completed `Simulation` and writes JSONL. Uses `sim.get_raw_log()`
   plus entity memory introspection. Called once after `sim.play()`.
2. **`dashboard.py`** — Streamlit app. `streamlit run dashboard.py --
   logs/sim_rooms_TIMESTAMP.jsonl`. Pure consumer of the log.
3. **Per-sim wiring** — one line at the end of each sim's `main()`:
   `shared.write_replay_log(sim, "logs/<name>_<ts>.jsonl")`.

### Open questions / deferred

- **Live mode** (file-watcher refresh during sim). Deferred — most
  use cases are forensic, not real-time.
- **Comparing two runs side-by-side.** Maybe v1.2.
- **Capturing the exact prompt sent to the LLM per turn** for layer 3.
  Need to look at whether Concordia exposes this without modifying
  the fork — probably requires a hook somewhere.
- **Works on upstream examples too?** Goal yes; depends on whether
  the writer can derive everything from `raw_log` + introspection
  without sim-specific setup. Test once MVP is working.
