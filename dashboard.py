"""Concordia replay dashboard.

Streamlit app that reads a per-turn JSONL log produced by
``shared.play_with_replay()`` and lets you scrub through the simulation
turn by turn. Per-entity memory cards show what each entity knew at
the selected turn; the event stream shows the full timeline with the
current turn highlighted.

Run:
  streamlit run dashboard.py

The dashboard auto-discovers JSONL files under ./logs/. Pick one from
the selector at the top. Use the turn slider to scrub.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st


LOG_DIR = Path("logs")
DEFAULT_RECENT_OBS = 8  # how many recent observations to show by default


# ----- Data loading ---------------------------------------------------


def list_replay_logs(log_dir: Path) -> list[Path]:
    """Return JSONL replay logs in `log_dir`, newest first."""
    if not log_dir.exists():
        return []
    return sorted(
        log_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


@st.cache_data(show_spinner=False)
def load_replay(path: str) -> list[dict]:
    """Load a JSONL replay log into a list of per-turn records.

    Cached by Streamlit on the path string so re-renders don't re-parse.
    """
    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


# ----- Layout ---------------------------------------------------------


def render_entity_card(name: str, memories: list[str], n_recent: int) -> None:
    """Render one entity's memory card."""
    st.markdown(f"### {name}")
    st.caption(f"{len(memories)} memories")

    if not memories:
        st.text("(no memories yet)")
        return

    recent = memories[-n_recent:]
    for mem in recent:
        st.text(mem)

    if len(memories) > n_recent:
        with st.expander(f"Full memory ({len(memories)} entries)"):
            for mem in memories:
                st.text(mem)


def render_event_stream(records: list[dict], current_idx: int) -> None:
    """Render the linear event stream with the current turn highlighted."""
    for i, rec in enumerate(records):
        turn = rec.get("turn", "?")
        actor = rec.get("actor") or "(unknown)"
        action = rec.get("action") or ""
        # Trim long actions for the overview view
        action_preview = action[:200] + ("..." if len(action) > 200 else "")
        is_current = i == current_idx

        if is_current:
            st.markdown(
                f"**▶ Turn {turn} — {actor}**  \n{action_preview}"
            )
        else:
            st.markdown(
                f"<span style='color:#888'>Turn {turn} — {actor}: "
                f"{action_preview}</span>",
                unsafe_allow_html=True,
            )


# ----- Main -----------------------------------------------------------


def main() -> None:
    st.set_page_config(
        layout="wide", page_title="Concordia Replay", page_icon="🎬"
    )
    st.title("Concordia Replay")

    logs = list_replay_logs(LOG_DIR)
    if not logs:
        st.error(
            f"No `.jsonl` replay logs found under `{LOG_DIR}/`. Run a "
            "sim with `shared.play_with_replay(...)` to produce one."
        )
        st.stop()

    selected_log = st.selectbox(
        "Replay log",
        options=logs,
        format_func=lambda p: p.name,
    )
    records = load_replay(str(selected_log))
    if not records:
        st.error(f"Log `{selected_log.name}` is empty.")
        st.stop()

    # Turn slider — default to the final turn so the dashboard opens on
    # "end of simulation" state, but the user can scrub back.
    n_turns = len(records)
    if n_turns == 1:
        turn_idx = 0
        st.markdown(f"**Turn 1 of 1** (only one step in this log)")
    else:
        turn_idx = st.slider(
            "Turn",
            min_value=0,
            max_value=n_turns - 1,
            value=n_turns - 1,
            format="step %d",
        )

    record = records[turn_idx]

    # Header summary
    turn_num = record.get("turn", turn_idx + 1)
    actor = record.get("actor") or "(unknown)"
    gm = record.get("game_master") or "(unknown)"
    action = record.get("action") or ""

    st.markdown(
        f"### Turn {turn_num} — {actor}  \n"
        f"<span style='color:#888'>GM: {gm}</span>",
        unsafe_allow_html=True,
    )
    if action:
        st.markdown(f"**Action:** {action}")

    # Sidebar: settings
    with st.sidebar:
        st.markdown("### Display settings")
        n_recent = st.slider(
            "Recent observations per entity",
            min_value=3,
            max_value=30,
            value=DEFAULT_RECENT_OBS,
        )
        st.markdown("---")
        st.markdown(f"**Log:** `{selected_log.name}`")
        st.markdown(f"**Total turns:** {n_turns}")
        st.markdown(f"**Entities tracked:** {len(record.get('memories', {}))}")

    # Entity cards row
    memories = record.get("memories", {})
    entity_names = list(memories.keys())
    if entity_names:
        cols = st.columns(len(entity_names))
        for col, name in zip(cols, entity_names):
            with col:
                render_entity_card(name, memories[name], n_recent)

    # Event stream
    st.divider()
    st.subheader("Event stream")
    render_event_stream(records, turn_idx)


if __name__ == "__main__":
    main()
