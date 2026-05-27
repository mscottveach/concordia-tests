"""Shared helpers used by every simulation in this folder.

Provides a single place for provider-switching (Anthropic / OpenRouter /
OpenAI), embedder setup, and per-run logging, so individual simulation
files stay focused on what they're simulating.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Callable

import numpy as np
from dotenv import load_dotenv

from concordia.contrib import language_models as concordia_models
from concordia.language_model import language_model as language_model_lib

# Load API keys from .env at the project root (same dir as this file).
# Existing shell env vars take precedence — .env only fills in what's missing.
load_dotenv(dotenv_path=Path(__file__).parent / ".env")


# Provider presets: api_type -> default model_name + env var holding the key.
# Add more here as needed.
_PROVIDER_PRESETS = {
    "anthropic": {
        "default_model": "claude-haiku-4-5-20251001",
        "key_env": "ANTHROPIC_API_KEY",
    },
    "openrouter": {
        "default_model": "anthropic/claude-haiku-4-5",
        "key_env": "OPENROUTER_API_KEY",
    },
    "openai": {
        "default_model": "gpt-5",
        "key_env": "OPENAI_API_KEY",
    },
}


def make_model(
    provider: str = "anthropic",
    model_name: str | None = None,
) -> language_model_lib.LanguageModel:
    """Build a Concordia language model.

    Args:
      provider: One of 'anthropic', 'openrouter', 'openai' (or any other key
        registered in concordia.contrib.language_models._REGISTRY).
      model_name: Override the default model for this provider.

    Returns:
      A Concordia LanguageModel ready to pass into a Simulation.
    """
    preset = _PROVIDER_PRESETS.get(provider, {})
    model_name = model_name or preset.get("default_model")
    if model_name is None:
        raise ValueError(
            f"No default model for provider {provider!r}. Pass model_name explicitly."
        )
    api_key = os.getenv(preset.get("key_env", "")) if preset else None
    return concordia_models.language_model_setup(
        api_type=provider,
        model_name=model_name,
        api_key=api_key,
    )


def make_embedder() -> Callable[[str], np.ndarray]:
    """Build a sentence-embedder for AssociativeMemory.

    Uses sentence-transformers locally (no API key needed).
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(text: str) -> np.ndarray:
        return np.asarray(model.encode(text))

    return embed


# Strips ANSI color escape sequences (e.g. from termcolor) so captured
# stdout is clean when written to a plain-text/markdown file.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class TeeStdout:
    """Context manager that mirrors stdout to a buffer.

    The buffered copy always receives everything (ANSI-stripped), suitable
    for dropping into a markdown log. The real terminal optionally receives
    only lines that pass a filter, so you can keep the live view focused
    on actions/outcomes while still capturing full detail in the log.

    Usage (no filtering — terminal sees everything):
        with TeeStdout() as captured:
            something_that_prints()

    Usage (filter terminal output):
        def keep(line: str) -> bool:
            return "chose action:" in line

        with TeeStdout(terminal_filter=keep) as captured:
            something_that_prints()
    """

    def __init__(
        self,
        terminal_filter: Callable[[str], bool] | None = None,
        terminal_separator: str = "",
    ) -> None:
        self._buffer = StringIO()
        self._original: Any = None
        self._terminal_filter = terminal_filter
        # Written to the terminal after each line that passes the filter.
        # Set to "\n" to get a blank line between matched entries.
        self._terminal_separator = terminal_separator
        # When a filter is set we line-buffer terminal output so we filter
        # on complete lines, not on the partial text fragments that print()
        # emits across multiple write() calls.
        self._terminal_line_buffer = ""

    def __enter__(self) -> TeeStdout:
        self._original = sys.stdout
        sys.stdout = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # Flush any trailing partial line through the filter on the way out.
        if self._terminal_filter is not None and self._terminal_line_buffer:
            plain = _ANSI_ESCAPE_RE.sub("", self._terminal_line_buffer)
            if self._terminal_filter(plain):
                self._original.write(self._terminal_line_buffer)
                if self._terminal_separator:
                    self._original.write(self._terminal_separator)
            self._terminal_line_buffer = ""
        sys.stdout = self._original
        return False

    def write(self, text: str) -> int:
        # The log buffer always receives everything.
        self._buffer.write(_ANSI_ESCAPE_RE.sub("", text))

        if self._terminal_filter is None:
            self._original.write(text)
            return len(text)

        # Line-buffered, filtered terminal output.
        self._terminal_line_buffer += text
        while "\n" in self._terminal_line_buffer:
            idx = self._terminal_line_buffer.index("\n")
            line = self._terminal_line_buffer[: idx + 1]
            self._terminal_line_buffer = self._terminal_line_buffer[idx + 1 :]
            plain = _ANSI_ESCAPE_RE.sub("", line)
            if self._terminal_filter(plain):
                self._original.write(line)
                if self._terminal_separator:
                    self._original.write(self._terminal_separator)
        return len(text)

    def flush(self) -> None:
        self._original.flush()

    def getvalue(self) -> str:
        return self._buffer.getvalue()


def write_sim_log(
    *,
    name: str,
    terminal_output: str,
    sim_log: Any,
    metadata: dict[str, Any],
    log_dir: str | Path = "logs",
) -> Path:
    """Write a per-run markdown log capturing terminal output + sim state.

    Args:
      name: Short name for the sim (used in filename, e.g. "sim_pub").
      terminal_output: Captured stdout (ANSI already stripped).
      sim_log: The SimulationLog object returned by sim.play(). May be None.
      metadata: Dict of run metadata (provider, model, premise, etc.) — each
        key/value rendered as a bullet under the Metadata heading.
      log_dir: Directory to write into. Created if it doesn't exist.

    Returns:
      Path to the written markdown file.
    """
    now = datetime.now()
    file_ts = now.strftime("%Y%m%d-%H%M%S")
    header_ts = now.strftime("%Y-%m-%d %H:%M:%S")

    out_dir = Path(log_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}_{file_ts}.md"

    parts: list[str] = [f"# {name} run — {header_ts}", ""]

    parts.append("## Metadata")
    parts.append("")
    for key, value in metadata.items():
        parts.append(f"- **{key}**: {value}")
    parts.append("")

    parts.append("## Terminal output")
    parts.append("")
    parts.append("```text")
    parts.append(terminal_output.rstrip())
    parts.append("```")
    parts.append("")

    summary = sim_log.get_summary() if sim_log is not None else None
    if summary:
        parts.append("## Summary")
        parts.append("")
        for key, value in summary.items():
            parts.append(f"- **{key}**: {value}")
        parts.append("")

    # SimulationLog stores these as private attrs populated by Simulation.play().
    entity_memories = (
        getattr(sim_log, "_entity_memories", {}) if sim_log is not None else {}
    )
    if entity_memories:
        parts.append("## Entity memories")
        parts.append("")
        for entity_name, memories in entity_memories.items():
            parts.append(f"### {entity_name}")
            parts.append("")
            for mem in memories:
                parts.append(f"- {mem}")
            parts.append("")

    gm_memories = (
        getattr(sim_log, "_game_master_memories", []) if sim_log is not None else []
    )
    if gm_memories:
        parts.append("## Game master memories")
        parts.append("")
        for mem in gm_memories:
            parts.append(f"- {mem}")
        parts.append("")

    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def write_trace_log(
    *,
    name: str,
    raw_log: list[Any],
    metadata: dict[str, Any],
    log_dir: str | Path = "logs",
) -> Path:
    """Write a per-step trace markdown of component contributions and prompts.

    Walks the raw_log produced by ``sim.play(raw_log=...)`` and emits a
    breakdown for every step — every component's pre_act output, the final
    prompts sent to the model, and the model's responses — for both entity
    acts and the GM's per-phase calls.

    Returns the path to the written file.
    """
    now = datetime.now()
    file_ts = now.strftime("%Y%m%d-%H%M%S")
    header_ts = now.strftime("%Y-%m-%d %H:%M:%S")

    out_dir = Path(log_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}_{file_ts}_trace.md"

    parts: list[str] = [f"# {name} trace — {header_ts}", ""]
    parts.append("## Metadata")
    parts.append("")
    for key, value in metadata.items():
        parts.append(f"- **{key}**: {value}")
    parts.append("")
    parts.append("## Trace")
    parts.append("")
    parts.extend(_format_trace_body(raw_log))

    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def _format_trace_body(raw_log: list[Any]) -> list[str]:
    lines: list[str] = []
    for entry in raw_log:
        if not isinstance(entry, dict):
            continue
        step = entry.get("Step", "?")
        lines.append(f"### Step {step}")
        lines.append("")
        for key, value in entry.items():
            if key in ("Step", "Summary", "date", "thread"):
                continue
            if "Entity" in key:
                entity_name = key.replace("Entity [", "").replace("]", "").strip()
                lines.append(f"#### Entity acts — {entity_name}")
                lines.append("")
                lines.extend(_format_components_block(value))
            else:
                gm_name = key.split(" --- ")[0]
                lines.append(f"#### Game master — `{gm_name}`")
                lines.append("")
                lines.extend(_format_gm_log_entry(value))
    return lines


def _format_gm_log_entry(value: Any) -> list[str]:
    """The GM log_entry is a dict of phase → data; render each phase."""
    lines: list[str] = []
    if not isinstance(value, dict):
        lines.append(f"> {value}")
        lines.append("")
        return lines

    for phase, phase_data in value.items():
        if not phase_data:
            continue
        lines.append(f"**Phase: `{phase}`**")
        lines.append("")
        # make_observation is nested one extra level: entity_name → components
        if phase == "make_observation" and isinstance(phase_data, dict) and all(
            isinstance(v, dict) for v in phase_data.values()
        ):
            for entity_name, entity_data in phase_data.items():
                lines.append(f"*Observation to {entity_name}:*")
                lines.append("")
                lines.extend(_format_components_block(entity_data))
        else:
            lines.extend(_format_components_block(phase_data))
    return lines


def _format_components_block(value: Any) -> list[str]:
    """Render a {component_name: component_data} mapping."""
    lines: list[str] = []
    if not isinstance(value, dict):
        lines.append(f"> {value}")
        lines.append("")
        return lines

    for component_name, comp_data in value.items():
        lines.extend(_format_component_data(component_name, comp_data))
    return lines


def _format_component_data(name: str, data: Any) -> list[str]:
    """Render a single component's logged datum."""
    lines = [f"**`{name}`**"]
    if isinstance(data, dict):
        # Pull known fields first in a stable order, then anything else.
        summary = data.get("Summary")
        if summary:
            lines.append(f"Summary: {summary}")
        value = data.get("Value")
        if value is not None and str(value).strip():
            lines.append(f"> {value}")
        prompt = data.get("Prompt")
        if prompt:
            prompt_text = (
                "\n".join(prompt) if isinstance(prompt, list) else str(prompt)
            )
            lines.append("")
            lines.append("<details>")
            lines.append("<summary>Full prompt sent to model</summary>")
            lines.append("")
            lines.append("```text")
            lines.append(prompt_text)
            lines.append("```")
            lines.append("")
            lines.append("</details>")
        # Anything else (debug, choices_calls, etc.) gets dumped at the end.
        for key, val in data.items():
            if key in ("Summary", "Value", "Prompt"):
                continue
            lines.append(f"- {key}: {val}")
    elif data is None:
        lines.append("_(no data)_")
    else:
        lines.append(f"> {data}")
    lines.append("")
    return lines


# Palette for character name colors in the story HTML. Tuned to be readable
# on the dark background used by write_story_html.
_CHARACTER_COLORS = [
    "#e88a96",  # rose
    "#8ab0d6",  # slate blue
    "#a8d290",  # moss green
    "#dba978",  # ochre
    "#b89ad0",  # plum
    "#7ec8c8",  # teal
]


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _extract_turns(raw_log: list[Any]) -> list[tuple[int, str, str]]:
    """Pull (step, entity_name, action_text) tuples from raw_log in order.

    Strips the redundant leading "<name>: " prefix from action text, since
    we render the speaker name separately.
    """
    turns: list[tuple[int, str, str]] = []
    for entry in raw_log:
        if not isinstance(entry, dict):
            continue
        step = entry.get("Step", 0)
        for key, value in entry.items():
            if key in ("Step", "Summary", "date", "thread"):
                continue
            if "Entity [" not in key:
                continue
            entity_name = key.replace("Entity [", "").replace("]", "").strip()
            if not isinstance(value, dict):
                continue
            act_data = value.get("__act__")
            if not isinstance(act_data, dict):
                continue
            action = act_data.get("Value", "")
            if not action:
                continue
            # Strip a single leading "<name>: " prefix if present, since we
            # render the speaker name in its own styled element.
            prefix = f"{entity_name}: "
            if action.startswith(prefix):
                action = action[len(prefix):]
            # Also strip a leading bare name + space if the model echoed it.
            if action.startswith(f"{entity_name} "):
                action = action[len(entity_name) + 1:]
            turns.append((step, entity_name, action.strip()))
    return turns


def write_story_html(
    *,
    name: str,
    raw_log: list[Any],
    metadata: dict[str, Any],
    log_dir: str | Path = "logs",
) -> Path:
    """Write a styled HTML story-reader view of the simulation.

    Includes only the things needed to follow the story: the opening
    premise, and each resolved entity action in order. No observations,
    no GM internals, no scene-start premises.
    """
    now = datetime.now()
    file_ts = now.strftime("%Y%m%d-%H%M%S")
    header_ts = now.strftime("%Y-%m-%d %H:%M:%S")

    out_dir = Path(log_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}_{file_ts}.html"

    turns = _extract_turns(raw_log)

    # Assign each entity a stable color from the palette, in first-seen order.
    name_to_color: dict[str, str] = {}
    for _, entity_name, _ in turns:
        if entity_name not in name_to_color:
            name_to_color[entity_name] = _CHARACTER_COLORS[
                len(name_to_color) % len(_CHARACTER_COLORS)
            ]

    premise = metadata.get("premise", "")

    # Build per-character CSS rules for speaker colors.
    speaker_rules = "\n".join(
        f"    .speaker[data-name='{_html_escape(n)}'] {{ color: {c}; }}"
        for n, c in name_to_color.items()
    )

    # Build the turn list as HTML.
    turn_blocks: list[str] = []
    for _, entity_name, action in turns:
        safe_action = _html_escape(action).replace("\n\n", "</p><p>")
        turn_blocks.append(
            f'    <div class="turn">\n'
            f'      <div class="speaker" data-name="{_html_escape(entity_name)}">'
            f'{_html_escape(entity_name)}</div>\n'
            f'      <div class="action"><p>{safe_action}</p></div>\n'
            f'    </div>'
        )
    turns_html = "\n".join(turn_blocks)

    # Compact metadata footer.
    meta_pairs = [(k, v) for k, v in metadata.items() if k != "premise"]
    meta_html = " &middot; ".join(
        f"<span class='meta-key'>{_html_escape(str(k))}:</span> "
        f"{_html_escape(str(v))}"
        for k, v in meta_pairs
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{_html_escape(name)} — {header_ts}</title>
<style>
    html, body {{
        background: #1a1a1a;
    }}
    body {{
        font-family: Georgia, 'Times New Roman', serif;
        max-width: 720px;
        margin: 3em auto;
        padding: 0 1.5em 4em;
        line-height: 1.7;
        color: #d8d6cf;
    }}
    h1 {{
        font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
        font-weight: 500;
        font-size: 1.4em;
        color: #f0ede5;
        margin-bottom: 0.2em;
    }}
    .timestamp {{
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 0.85em;
        color: #777;
        margin-bottom: 2.5em;
    }}
    .premise {{
        font-style: italic;
        color: #b0a99e;
        border-left: 3px solid #4a4639;
        padding: 0.3em 0 0.3em 1.2em;
        margin: 2em 0 3em;
        font-size: 1.05em;
    }}
    .turn {{
        margin: 2em 0;
    }}
    .speaker {{
        font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
        font-weight: 600;
        font-size: 0.95em;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.3em;
    }}
{speaker_rules}
    .action {{
        margin-left: 0;
    }}
    .action p {{
        margin: 0.6em 0;
    }}
    footer {{
        margin-top: 5em;
        padding-top: 1.5em;
        border-top: 1px solid #3a3835;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 0.75em;
        color: #777;
    }}
    .meta-key {{
        font-weight: 600;
        color: #999;
    }}
</style>
</head>
<body>
    <h1>{_html_escape(name)}</h1>
    <div class="timestamp">{header_ts}</div>
    <div class="premise">{_html_escape(premise)}</div>
{turns_html}
    <footer>{meta_html}</footer>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
    return path
