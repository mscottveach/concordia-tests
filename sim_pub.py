"""Minimal two-agent conversation in a pub.

Demonstrates the smallest viable Concordia simulation:
  - Two basic entities (Alice, Bob)
  - A dialogic Game Master managing turn-taking
  - Free-text actions, no scenes, no scoring

Run:
  python sim_pub.py
  python sim_pub.py --provider openrouter
  python sim_pub.py --provider anthropic --model claude-sonnet-4-6
"""

from __future__ import annotations

import argparse

from concordia.prefabs import entity as entity_prefabs
from concordia.prefabs import game_master as game_master_prefabs
from concordia.prefabs.simulation import generic as simulation
from concordia.typing import entity as entity_lib
from concordia.typing import prefab as prefab_lib
from concordia.typing import scene as scene_lib
from concordia.utils import helper_functions

import shared


PREMISE = (
    "Alice and Bob are strangers who happen to share a small table at a "
    "crowded London pub on a rainy evening. The conversation begins."
)
MAX_STEPS = 20


def _terminal_filter(line: str) -> bool:
  """Decide whether a line should appear in the live terminal.

  Everything is still written to the markdown log; this just keeps the
  terminal view focused on the conversation rather than the engine's
  internal bookkeeping (observations, GM switches, action specs, etc.).
  """
  return (
      line.startswith("[sim_pub]")
      or "The resolved event was:" in line
  )


def build_scenes() -> list[scene_lib.SceneSpec]:
  """Four-scene arc: small talk → recognition → reckoning → second-chance.

  Each scene runs for a fixed number of rounds, then advances. At each
  scene boundary, the per-entity ``premise`` strings are pushed into that
  entity's memory as observations (see scene_tracker._maybe_queue_scene_
  start_premises). The per-scene ``call_to_action`` becomes the question
  asked of whoever is acting that turn — that's where we shape the beat.
  """
  participants = ("Alice", "Bob")

  def _free_action(call_to_action: str) -> entity_lib.ActionSpec:
    return entity_lib.free_action_spec(call_to_action=call_to_action)

  small_talk = scene_lib.SceneSpec(
      scene_type=scene_lib.SceneTypeSpec(
          name="small_talk",
          game_master_name="conversation rules",
          action_spec=_free_action(
              "Given the conversation so far, what does {name} say next?"
          ),
      ),
      participants=participants,
      num_rounds=3,
      premise={name: [] for name in participants},
  )

  the_recognition = scene_lib.SceneSpec(
      scene_type=scene_lib.SceneTypeSpec(
          name="the_recognition",
          game_master_name="conversation rules",
          action_spec=_free_action(
              "Given everything {name} has heard so far, does anything "
              "click? What does {name} say next?"
          ),
      ),
      participants=participants,
      num_rounds=2,
      premise={
          "Alice": [
              "Alice is now certain — same dark hair, same slight "
              "London accent, mid-forties, even the way he glances at "
              "his glass. This is the Bob from the Tinder date. She "
              "decides this is the moment to bring it up, gently."
          ],
          "Bob": [
              "Something about the woman across from him has been "
              "nagging at Bob for the last few minutes — a vague sense "
              "he's met her before, though he can't yet place where."
          ],
      },
  )

  the_reckoning = scene_lib.SceneSpec(
      scene_type=scene_lib.SceneTypeSpec(
          name="the_reckoning",
          game_master_name="conversation rules",
          action_spec=_free_action(
              "Now that the past is on the table, how does {name} respond "
              "— defensively, honestly, or somewhere in between? What does "
              "{name} say next?"
          ),
      ),
      participants=participants,
      num_rounds=4,
      premise={
          "Alice": [
              "Alice's first instinct is to remember how dismissive Bob "
              "was that night — barely looking up from his phone. But "
              "she also remembers, more uncomfortably, how sharp and "
              "sarcastic she got in response."
          ],
          "Bob": [
              "Bob's first instinct is to defend himself — he'd had a "
              "brutal week. But he also remembers, with growing "
              "discomfort, exactly how checked-out he was that night, "
              "and how unfair that was to her."
          ],
      },
  )

  second_chance = scene_lib.SceneSpec(
      scene_type=scene_lib.SceneTypeSpec(
          name="second_chance",
          game_master_name="conversation rules",
          action_spec=_free_action(
              "Reflecting on the strange coincidence of ending up at the "
              "same table tonight, what does {name} say?"
          ),
      ),
      participants=participants,
      num_rounds=2,
      premise={
          name: [
              "The conversation has reached an unexpectedly honest "
              "place. Both of them are quietly wondering whether "
              "tonight, of all nights, means anything."
          ]
          for name in participants
      },
  )

  return [small_talk, the_recognition, the_reckoning, second_chance]


def build_config() -> prefab_lib.Config:
  prefabs = {
      **helper_functions.get_package_classes(entity_prefabs),
      **helper_functions.get_package_classes(game_master_prefabs),
  }

  instances = [
      prefab_lib.InstanceConfig(
          prefab="basic__Entity",
          role=prefab_lib.Role.ENTITY,
          params={
              "name": "Alice",
              "goal": (
                  "Alice is almost certain the man across from her is the "
                  "Bob from that disastrous Tinder date a year ago, but "
                  "she wants to be sure before she says anything. She "
                  "makes small talk and watches for confirmation — his "
                  "accent, his mannerisms, anything she remembers. If "
                  "she becomes sure it's him, she'll find a moment to "
                  "ask whether he remembers her — not as a gotcha, but "
                  "out of honest curiosity. She isn't angry. She just "
                  "realized she wants to know how he sees that night now."
              ),
          },
      ),
      prefab_lib.InstanceConfig(
          prefab="basic__Entity",
          role=prefab_lib.Role.ENTITY,
          params={
              "name": "Bob",
              "goal": (
                  "Bob is tired and came in for a quiet pint, not a "
                  "conversation. He is polite but doesn't volunteer much; "
                  "he lets the other person carry the talk. When "
                  "something uncomfortable comes up, his first instinct "
                  "is to deflect or rationalize — but he has a habit of "
                  "eventually owning it when he realizes he was in the "
                  "wrong."
              ),
          },
      ),
      prefab_lib.InstanceConfig(
          prefab="formative_memories_initializer__GameMaster",
          role=prefab_lib.Role.INITIALIZER,
          params={
              "name": "initial setup",
              "next_game_master_name": "conversation rules",
              "shared_memories": [
                  "It is a Tuesday evening in late October. A steady rain "
                  "has been falling for hours.",
                  "We are inside The Lamb and Flag, a small pub tucked down "
                  "a side street in Covent Garden, London.",
                  "The pub is crowded tonight — everyone driven inside by "
                  "the weather. Most tables are full; the air is warm and "
                  "smells of beer and damp wool.",
                  "We are sharing a small wooden table near the back because "
                  "no other seats were free.",
              ],
              # Each list entry becomes a memory line for that player and is
              # also pushed as an observation. player_specific_context is the
              # alternative path but it's only consumed inside the LLM
              # backstory generator, which we skip below — so we use
              # player_specific_memories to inject backstory directly.
              "player_specific_memories": {
                  "Alice": [
                      "Alice is a 32-year-old PhD student in linguistics, "
                      "recently moved to London from Toronto. She is curious "
                      "about people and tends to ask questions.",
                      "A year ago Alice went on a Tinder date with a man "
                      "named Bob — same dark hair, slight London accent, "
                      "mid-forties. It was a disaster: he barely looked up "
                      "from his phone the whole night, she got brittle and "
                      "sarcastic in response, and they left without saying "
                      "goodnight. She hasn't thought about him in months, "
                      "but she'd recognize him anywhere.",
                  ],
                  "Bob": [
                      "Bob is a 45-year-old freelance graphic designer who "
                      "grew up in London. He had a long day and came to the "
                      "pub for a quiet pint, alone.",
                      "Sometime last year Bob went on a Tinder date that "
                      "didn't go well. He'd been having a brutal week at "
                      "work and wasn't really present — he kept checking "
                      "his phone, then the woman got sharp with him, and "
                      "they left annoyed. He felt vaguely guilty afterwards "
                      "but moved on. He doesn't remember her name or her "
                      "face clearly.",
                  ],
              },
              "skip_formative_memories_for": ["Alice", "Bob"],
          },
      ),
      prefab_lib.InstanceConfig(
          prefab="dialogic_and_dramaturgic__GameMaster",
          role=prefab_lib.Role.GAME_MASTER,
          params={
              "name": "conversation rules",
              "scenes": build_scenes(),
          },
      ),
  ]

  return prefab_lib.Config(
      default_premise=PREMISE,
      default_max_steps=MAX_STEPS,
      prefabs=prefabs,
      instances=instances,
  )


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument(
      "--provider",
      default="anthropic",
      help="LLM provider: anthropic | openrouter | openai (default: anthropic)",
  )
  parser.add_argument(
      "--model",
      default=None,
      help="Override the default model name for the chosen provider.",
  )
  args = parser.parse_args()

  metadata = {
      "provider": args.provider,
      "model": args.model or "(default)",
      "premise": PREMISE,
      "max_steps": MAX_STEPS,
  }

  raw_log: list = []

  with shared.TeeStdout(
      terminal_filter=_terminal_filter,
      terminal_separator="\n",
  ) as captured:
    print(
        f"[sim_pub] provider={args.provider} "
        f"model={args.model or '(default)'}"
    )
    model = shared.make_model(provider=args.provider, model_name=args.model)
    embedder = shared.make_embedder()
    config = build_config()
    sim = simulation.Simulation(config=config, model=model, embedder=embedder)
    print("[sim_pub] running...")
    result = sim.play(raw_log=raw_log)
    print("[sim_pub] done")

  log_path = shared.write_sim_log(
      name="sim_pub",
      terminal_output=captured.getvalue(),
      sim_log=result,
      metadata=metadata,
  )
  # trace_path = shared.write_trace_log(
  #     name="sim_pub",
  #     raw_log=raw_log,
  #     metadata=metadata,
  # )
  story_path = shared.write_story_html(
      name="sim_pub",
      raw_log=raw_log,
      metadata=metadata,
  )
  print(f"[sim_pub] log written:   {log_path}")
  print(f"[sim_pub] story written: {story_path}")


if __name__ == "__main__":
  main()
