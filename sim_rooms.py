"""Two characters in adjacent locked rooms solve a puzzle by talking through the wall.

Premise: Quinn and Sam are in two identical, sealed rooms. Each has a
puzzle on a panel — Quinn's room has the puzzle in the right order but
the wrong colors; Sam's has the right colors but the wrong order. They
can hear each other through the wall. The door opens only when the
puzzle is correct.

Run:
  python sim_rooms.py
  python sim_rooms.py --provider openrouter
  python sim_rooms.py --provider openrouter --model anthropic/claude-opus-4.7
"""

from __future__ import annotations

import argparse

from concordia.contrib.components.game_master import game_mechanic
from concordia.prefabs import entity as entity_prefabs
from concordia.prefabs import game_master as game_master_prefabs
from concordia.prefabs.simulation import generic as simulation
from concordia.typing import entity as entity_lib
from concordia.typing import prefab as prefab_lib
from concordia.typing import scene as scene_lib
from concordia.utils import helper_functions

import shared
import sim_rooms_puzzle as puzzle


PREMISE = (
    "Quinn and Sam are in two adjacent, identical rooms. Each room has "
    "a single door, sealed. There is no window, no other exit. Neither "
    "knows the other is there until they hear movement through the wall. "
    "On a panel mounted in each room sits a puzzle — incomplete, in "
    "different ways. The door will open only when the puzzle is correctly "
    "arranged."
)
MAX_STEPS = 45


def _terminal_filter(line: str) -> bool:
  """Decide whether a line should appear in the live terminal."""
  return (
      line.startswith("[sim_rooms]")
      or "The resolved event was:" in line
  )


def build_scenes() -> list[scene_lib.SceneSpec]:
  """Placeholder — single scene running the full budget."""
  participants = ("Quinn", "Sam")

  def _free_action(call_to_action: str) -> entity_lib.ActionSpec:
    return entity_lib.free_action_spec(call_to_action=call_to_action)

  opening = scene_lib.SceneSpec(
      scene_type=scene_lib.SceneTypeSpec(
          name="opening",
          game_master_name="conversation rules",
          action_spec=_free_action(
              "Given the conversation so far, what does {name} say next?"
          ),
      ),
      participants=participants,
      num_rounds=MAX_STEPS,
      premise={name: [] for name in participants},
  )

  return [opening]


def build_config(model) -> prefab_lib.Config:
  prefabs = {
      **helper_functions.get_package_classes(entity_prefabs),
      **helper_functions.get_package_classes(game_master_prefabs),
  }

  puzzle_mechanic = game_mechanic.GameMechanic(
      initial_state=puzzle.INITIAL_STATE,
      parse_event=puzzle.make_parser(model),
      observation_for=puzzle.observe,
      is_won=puzzle.is_won,
      won_narration=puzzle.WON_NARRATION,
      pre_act_label="\nPuzzle state",
      render_state=puzzle.render_state,
  )

  instances = [
      prefab_lib.InstanceConfig(
          prefab="basic__Entity",
          role=prefab_lib.Role.ENTITY,
          params={
              "name": "Quinn",
              "goal": (
                  "Quinn wants to understand her situation and find a "
                  "way out if she's locked in."
              ),
          },
      ),
      prefab_lib.InstanceConfig(
          prefab="basic__Entity",
          role=prefab_lib.Role.ENTITY,
          params={
              "name": "Sam",
              "goal": (
                  "Sam wants to figure out what this place is and how "
                  "to leave it."
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
                  "You are in a small, windowless room. Concrete walls, "
                  "one door.",
                  "Mounted on one wall is a panel. On the panel: six "
                  "shapes in a row of slots.",
                  "You can hear someone moving in the room next door, "
                  "through the wall.",
                  "If you speak up, sound passes through clearly enough "
                  "to be heard.",
              ],
              # TODO: fill in once we walk through per-character memories.
              "player_specific_memories": {
                  "Quinn": [
                      "Quinn is in her mid-thirties, a software engineer "
                      "by trade. She's the kind of person who reads "
                      "instruction manuals and makes spreadsheets for "
                      "fun. When something seems wrong, she looks for "
                      "patterns and asks careful questions before acting.",
                      "Quinn's panel: six shapes mounted in fixed slots, "
                      "left to right — a circle, a square, a triangle, a "
                      "hexagon, a star, and a diamond. The shapes are "
                      "colorless: gray outlines. Beside the panel is a "
                      "small device with six colored buttons — red, "
                      "orange, yellow, green, blue, purple — that can "
                      "assign colors to the shapes. The shapes "
                      "themselves cannot be moved.",
                  ],
                  "Sam": [
                      "Sam is in his early forties, a graphic designer. "
                      "He thinks visually first and notices when "
                      "something is aesthetically off before he can "
                      "explain why. Practical, hands-on, prefers to "
                      "figure things out by doing rather than planning.",
                      "Sam's panel: six shapes mounted on a sliding "
                      "rail. Left to right currently: a yellow triangle, "
                      "a red circle, a blue star, an orange square, a "
                      "purple diamond, a green hexagon. Each shape is "
                      "fixed in its color — the colors look intentional "
                      "and saturated. The shapes can be slid freely "
                      "along the rail. They cannot be recolored.",
                  ],
              },
              "skip_formative_memories_for": ["Quinn", "Sam"],
          },
      ),
      prefab_lib.InstanceConfig(
          prefab="dialogic_and_dramaturgic__GameMaster",
          role=prefab_lib.Role.GAME_MASTER,
          params={
              "name": "conversation rules",
              "scenes": build_scenes(),
              "extra_components": {"puzzle_mechanic": puzzle_mechanic},
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
        f"[sim_rooms] provider={args.provider} "
        f"model={args.model or '(default)'}"
    )
    model = shared.make_model(provider=args.provider, model_name=args.model)
    embedder = shared.make_embedder()
    config = build_config(model)
    sim = simulation.Simulation(config=config, model=model, embedder=embedder)
    print("[sim_rooms] running...")
    result = sim.play(raw_log=raw_log)
    print("[sim_rooms] done")

  log_path = shared.write_sim_log(
      name="sim_rooms",
      terminal_output=captured.getvalue(),
      sim_log=result,
      metadata=metadata,
  )
  story_path = shared.write_story_html(
      name="sim_rooms",
      raw_log=raw_log,
      metadata=metadata,
  )
  print(f"[sim_rooms] log written:   {log_path}")
  print(f"[sim_rooms] story written: {story_path}")


if __name__ == "__main__":
  main()
