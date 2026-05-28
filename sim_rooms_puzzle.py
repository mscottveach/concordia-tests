"""Puzzle logic for sim_rooms.

The state, transition rules, win check, and observation prose for the two-room
cooperative puzzle. Imported by sim_rooms.py and plugged into a `GameMechanic`
component on the GM.

Puzzle design:
  Quinn's panel has six shapes in FIXED slots (left to right): circle, square,
  triangle, hexagon, star, diamond. The shapes are colorless until Quinn
  assigns colors via her color buttons (red, orange, yellow, green, blue,
  purple). Quinn cannot move the shapes.

  Sam's panel has six shapes on a sliding rail, each fixed in its own color.
  Initial order: yellow triangle, red circle, blue star, orange square,
  purple diamond, green hexagon. Sam can slide them into any order but cannot
  recolor them.

  The door opens when both panels are arranged the same: Sam's shapes must be
  reordered to match Quinn's fixed slot order, and Quinn must color each shape
  to match the color of that same shape on Sam's panel.
"""

from __future__ import annotations

from concordia.document import interactive_document


SHAPES = ("circle", "square", "triangle", "hexagon", "star", "diamond")
COLORS = ("red", "orange", "yellow", "green", "blue", "purple")

# Sam's panel has these fixed shape-color pairings.
SAM_SHAPE_COLORS = {
    "circle": "red",
    "square": "orange",
    "triangle": "yellow",
    "hexagon": "green",
    "star": "blue",
    "diamond": "purple",
}

# The win state: Quinn's colors must match Sam's pairings AND Sam's order
# must match Quinn's fixed slot order.
TARGET_COLORS = dict(SAM_SHAPE_COLORS)
TARGET_ORDER = list(SHAPES)

INITIAL_STATE = {
    "quinn_colors": {shape: None for shape in SHAPES},
    "sam_order": ["triangle", "circle", "star", "square", "diamond", "hexagon"],
}

WON_NARRATION = (
    "[DOOR] A deep mechanical clunk echoes through both rooms. The seals "
    "release, and the doors swing open onto a shared corridor."
)


def render_state(state: dict) -> str:
  """Renders current puzzle state as labeled prose for prompt context."""
  quinn_lines = []
  for shape in SHAPES:
    color = state["quinn_colors"].get(shape) or "uncolored"
    quinn_lines.append(f"  - {shape}: {color}")
  sam_order = ", ".join(state["sam_order"])
  return (
      "Quinn's panel (shapes in fixed slots, left to right):\n"
      + "\n".join(quinn_lines)
      + f"\nSam's rail (current shape order, left to right): {sam_order}"
  )


def make_parser(model):
  """Returns a `parse_event(state, event)` closure that uses the LLM."""

  def parse(state: dict, event: str) -> dict | None:
    prompt = interactive_document.InteractiveDocument(model)
    prompt.statement(
        "Quinn has a panel with six shapes in fixed slots (left to right): "
        f"{', '.join(SHAPES)}. She can assign one of these colors to each: "
        f"{', '.join(COLORS)}. She cannot move shapes."
    )
    prompt.statement(
        "Sam has a rail of six pre-colored shapes that he can slide into "
        "any order. He cannot recolor them."
    )
    prompt.statement("Current puzzle state:")
    prompt.statement(render_state(state))
    prompt.statement(f"\nMost recent event in the simulation:\n{event}")

    try:
      anything_changed = prompt.yes_no_question(
          "During the most recent event above, did Quinn press a color "
          "button (assigning or changing a color), OR did Sam slide at "
          "least one shape into a new slot on his rail? Even a single "
          "color press or a single shape slide counts as a change. "
          "Pure talk with no physical interaction does NOT count."
      )
    except Exception as e:  # noqa: BLE001  defensive: LLM may return empty
      print(f'[puzzle] yes_no failed: {e!r}')  # DEBUG
      return None
    print(f'[puzzle] yes_no anything_changed: {anything_changed}')  # DEBUG
    if not anything_changed:
      return None

    try:
      colors_answer = prompt.open_question(
          "If Quinn assigned or changed any colors during this event, "
          "list the changes as 'shape:color' (one per change, "
          "comma-separated if more than one). If no color changes "
          "occurred this event, respond with the single word 'none'."
      )
    except Exception as e:  # noqa: BLE001
      print(f'[puzzle] colors_answer failed: {e!r}')  # DEBUG
      colors_answer = "none"
    print(f'[puzzle] colors_answer: {colors_answer!r}')  # DEBUG

    try:
      move_answer = prompt.open_question(
          "If Sam slid a single shape into a new slot during this event, "
          "respond as 'shape:slot_number' where slot_number is 1 through "
          "6 (left to right). For example, 'circle:1' means Sam moved "
          "the circle into the leftmost slot. If Sam moved more than one "
          "shape, list each move comma-separated. If Sam did not move "
          "any shape during this event, respond with the single word "
          "'none'."
      )
    except Exception as e:  # noqa: BLE001
      print(f'[puzzle] move_answer failed: {e!r}')  # DEBUG
      move_answer = "none"
    print(f'[puzzle] move_answer: {move_answer!r}')  # DEBUG

    new_state = {
        "quinn_colors": dict(state["quinn_colors"]),
        "sam_order": list(state["sam_order"]),
    }
    changed = False

    if colors_answer.strip().lower() != "none":
      for pair in colors_answer.split(","):
        if ":" not in pair:
          continue
        shape, color = pair.split(":", 1)
        shape = shape.strip().lower()
        color = color.strip().lower()
        if shape in SHAPES and color in COLORS:
          if new_state["quinn_colors"].get(shape) != color:
            new_state["quinn_colors"][shape] = color
            changed = True

    if move_answer.strip().lower() != "none":
      for move in move_answer.split(","):
        if ":" not in move:
          continue
        shape, slot_str = move.split(":", 1)
        shape = shape.strip().lower()
        slot_str = slot_str.strip()
        try:
          slot = int(slot_str)
        except ValueError:
          continue
        if shape in SHAPES and 1 <= slot <= 6:
          current_order = list(new_state["sam_order"])
          if shape in current_order:
            current_order.remove(shape)
            current_order.insert(slot - 1, shape)
          if current_order != new_state["sam_order"]:
            new_state["sam_order"] = current_order
            changed = True

    return new_state if changed else None

  return parse


def observe(old: dict, new: dict) -> dict:
  """Returns per-entity observation prose describing state changes."""
  observations = {}

  color_changes = []
  for shape in SHAPES:
    old_color = old["quinn_colors"].get(shape)
    new_color = new["quinn_colors"].get(shape)
    if old_color != new_color:
      if new_color is None:
        color_changes.append(f"the {shape} is no longer colored")
      else:
        color_changes.append(f"the {shape} now glows {new_color}")
  if color_changes:
    n_correct = sum(
        1
        for shape in SHAPES
        if new["quinn_colors"][shape] == TARGET_COLORS[shape]
    )
    full_panel = ", ".join(
        f"{shape}={new['quinn_colors'][shape] or 'uncolored'}"
        for shape in SHAPES
    )
    suffix = f"{n_correct} of 6 colors correctly assigned."
    if n_correct == 6 and not is_won(new):
      suffix += " Puzzle still incomplete."
    observations["Quinn"] = (
        f"[PANEL] You just pressed: {', '.join(color_changes)}. "
        f"Current panel: {full_panel}. {suffix}"
    )

  if old["sam_order"] != new["sam_order"]:
    n_correct = sum(
        1 for i, s in enumerate(new["sam_order"]) if s == TARGET_ORDER[i]
    )
    new_order = ", ".join(new["sam_order"])
    suffix = f"{n_correct} of 6 shapes in correct position."
    if n_correct == 6 and not is_won(new):
      suffix += " Puzzle still incomplete."
    observations["Sam"] = (
        f"[RAIL] Current rail order, left to right: {new_order}. {suffix}"
    )

  return observations


def is_won(state: dict) -> bool:
  """Win check: both panels match the target arrangement."""
  return (
      state["quinn_colors"] == TARGET_COLORS
      and state["sam_order"] == TARGET_ORDER
  )
