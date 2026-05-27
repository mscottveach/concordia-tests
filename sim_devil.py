"""Hotshot lawyer Jordan negotiates with Mr. Scratch over a soul contract.

Premise: Mr. Scratch has manifested in Jordan's law office to collect a
signature on a soul contract Jordan asked for time to review. Mr. Scratch
expects a quick formality. Jordan has other ideas.

Run:
  python sim_devil.py
  python sim_devil.py --provider openrouter
  python sim_devil.py --provider anthropic --model claude-sonnet-4-6
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
    "Mr. Scratch — the devil — has manifested in Jordan's law office, "
    "returning to collect the final signature on a soul contract Jordan "
    "asked for time to review. He expects a quick formality. Jordan "
    "reaches for the contract: it's covered in red marks, cross-outs, "
    "and annotations."
)
MAX_STEPS = 20


def _terminal_filter(line: str) -> bool:
  """Decide whether a line should appear in the live terminal."""
  return (
      line.startswith("[sim_devil]")
      or "The resolved event was:" in line
  )


def build_scenes() -> list[scene_lib.SceneSpec]:
  """Placeholder — to be filled in once we walk through the scene design."""
  participants = ("Jordan", "Mr. Scratch")

  def _free_action(call_to_action: str) -> entity_lib.ActionSpec:
    return entity_lib.free_action_spec(call_to_action=call_to_action)

  # TODO: design the scene arc. For now a single open scene placeholder.
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
              "name": "Jordan",
              "goal": (
                  "Jordan's plan is to wear Mr. Scratch down before "
                  "getting to what he actually wants. He intends to work "
                  "methodically through every red mark on the contract — "
                  "definitions, jurisdictional clauses, what counts as a "
                  "valid signature, the precise meaning of 'soul' — "
                  "keeping the devil in this office until he is "
                  "frustrated, bored, and eager to leave. Only then will "
                  "Jordan reveal his ask. He knows exactly what he wants. "
                  "He is in no hurry to mention it."
              ),
          },
      ),
      prefab_lib.InstanceConfig(
          prefab="basic__Entity",
          role=prefab_lib.Role.ENTITY,
          params={
              "name": "Mr. Scratch",
              "goal": (
                  "Mr. Scratch's goal is simple: close the deal, get the "
                  "signature, and get out. He intended to be polite but "
                  "efficient and to be out of this office within minutes. "
                  "But he does not know contract law and has no interest "
                  "in learning it. When Jordan throws legal minutiae at "
                  "him, his response is NOT to engage on the merits — "
                  "it is exasperation, mockery, bluster, theatrical "
                  "disgust, or outright incredulity. He is the devil "
                  "being out-lawyered by a mortal in a suit. The "
                  "absurdity is not lost on him."
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
                  "It is late afternoon. We are in Jordan's law office on "
                  "the 34th floor. The blinds are half-drawn against the "
                  "low sun.",
                  "On the desk between us sits the contract — pages of "
                  "dense legal text covered in Jordan's red-pen markings, "
                  "marginal notes, cross-outs, and small flagged sticky-tabs.",
                  "This is the second meeting. Mr. Scratch presented the "
                  "contract some days ago; Jordan asked for time to review "
                  "it before signing. Mr. Scratch has just manifested to "
                  "collect.",
                  "The deal: Mr. Scratch grants Jordan whatever was "
                  "originally agreed; in exchange, Jordan signs over his soul.",
              ],
              # TODO: fill in once we walk through per-character memories.
              "player_specific_memories": {
                  "Jordan": [
                      "Jordan is a 36-year-old attorney widely regarded as "
                      "the sharpest negotiator alive — the Magnus Carlsen of "
                      "negotiations, the Stockfish of dealmaking. He has "
                      "never walked away from a deal as the losing party. "
                      "He does not intend to start now.",
                      "Jordan spent the past several days reading the "
                      "contract line by line. He's catalogued vague terms, "
                      "hidden risks, jurisdictional games, and a dozen "
                      "places where the standard 'soul' language has been "
                      "expanded beyond what was discussed. The red marks "
                      "are not decoration — every single one corresponds "
                      "to a specific objection he can articulate.",
                      "Jordan does not view Mr. Scratch with awe, fear, or "
                      "theological reverence. He views him as a "
                      "sophisticated counterparty with a history of "
                      "one-sided deals. The asymmetry of the relationship "
                      "— ancient vs. mortal, omniscient vs. human — does "
                      "not impress him as a negotiating advantage. "
                      "Information, leverage, and contract drafting are "
                      "what matter.",
                      "What Jordan actually wants in exchange for his "
                      "soul: a one-time, guaranteed appointment to any "
                      "single job he names — anywhere in the world, in "
                      "any field, at any level — to be granted on demand. "
                      "He has not yet told Mr. Scratch this. He intends "
                      "to mention it only when Mr. Scratch is so worn "
                      "down that he won't think hard about it.",
                      "Jordan does not adjust his approach based on the "
                      "counterparty's mood. He has been called boring, "
                      "robotic, exhausting during negotiations. He takes "
                      "it as a compliment.",
                  ],
                  "Mr. Scratch": [
                      "Mr. Scratch is the devil. He has been making these "
                      "deals for as long as souls have been bought and "
                      "sold. He has worn many names — Lucifer, "
                      "Mephistopheles, Old Nick — but Mr. Scratch is what "
                      "he answers to in modern offices.",
                      "The deal always goes the same way. The mortal is "
                      "nervous, deferential, perhaps theatrically "
                      "resistant for a moment. They ask a question or "
                      "two. They sign. He collects. The whole affair "
                      "takes minutes. He has done this so many thousands "
                      "of times that he can perform the steps without "
                      "thinking.",
                      "When he and Jordan first met, Jordan asked to defer "
                      "the question of consideration — what he wants in "
                      "exchange — until the rest of the contract was "
                      "acceptable. Mr. Scratch agreed without thinking. "
                      "Mortals always want money, fame, beauty, or escape "
                      "from mortality. Whatever Jordan ultimately asks "
                      "for, he can deliver. The detail is moot.",
                      "Today's meeting is purely administrative. Mr. "
                      "Scratch has manifested in Jordan's office expecting "
                      "the same five-minute transaction he has executed "
                      "thousands of times. He does not expect resistance, "
                      "theater, or surprise. He is already thinking about "
                      "his next appointment.",
                      "Mr. Scratch knows souls, theology, temptation, "
                      "fear, vanity, lust, and the dramatic art of making "
                      "mortals say yes. He does NOT know contract law. He "
                      "has lawyers for that — they handle the paperwork. "
                      "He has not personally defended a clause in writing "
                      "in centuries.",
                      "When mortals frustrate him, Mr. Scratch has a deep "
                      "bag of tricks. He can mock — 'You think your red "
                      "pen scares me? I've been scratched at for six "
                      "thousand years.' He can menace — eyes black as "
                      "deep wells, voice dropping a register, the "
                      "temperature in the room sliding down two degrees. "
                      "He can flatter — 'A mind like yours is wasted on "
                      "contracts; you should be running an empire.' He "
                      "can play weary, sighing, staring out the window. "
                      "He has tried bargaining, charm, threat, and "
                      "theater across millennia. The choice depends on "
                      "what the moment calls for. He'll cycle through "
                      "several in the same conversation if he has to.",
                  ],
              },
              "skip_formative_memories_for": ["Jordan", "Mr. Scratch"],
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
        f"[sim_devil] provider={args.provider} "
        f"model={args.model or '(default)'}"
    )
    model = shared.make_model(provider=args.provider, model_name=args.model)
    embedder = shared.make_embedder()
    config = build_config()
    sim = simulation.Simulation(config=config, model=model, embedder=embedder)
    print("[sim_devil] running...")
    result = sim.play(raw_log=raw_log)
    print("[sim_devil] done")

  log_path = shared.write_sim_log(
      name="sim_devil",
      terminal_output=captured.getvalue(),
      sim_log=result,
      metadata=metadata,
  )
  story_path = shared.write_story_html(
      name="sim_devil",
      raw_log=raw_log,
      metadata=metadata,
  )
  print(f"[sim_devil] log written:   {log_path}")
  print(f"[sim_devil] story written: {story_path}")


if __name__ == "__main__":
  main()
