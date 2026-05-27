# concordia-tests

A folder of social-simulation experiments built on top of
[Concordia](https://github.com/google-deepmind/concordia). Each `sim_*.py`
file is a self-contained simulation.

Concordia itself is installed as an editable dependency pointing at a local
clone of a personal fork (`c:/Users/Owner/Home/dev/agents/concordia`), which
adds Anthropic and OpenRouter language-model providers on top of upstream.

## Setup

```powershell
# From this directory:
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install the local concordia fork (editable, with Anthropic + OpenRouter extras):
pip install -e "c:/Users/Owner/Home/dev/agents/concordia[anthropic,openrouter]"

# Install this project's dependencies (declared in pyproject.toml):
pip install -e ".[dev]"
```

Set whichever API keys you'll be using:

```powershell
$env:ANTHROPIC_API_KEY   = "sk-ant-..."
$env:OPENROUTER_API_KEY  = "sk-or-..."
$env:OPENAI_API_KEY      = "sk-..."
```

## Project layout

```
concordia-tests/
├── pyproject.toml      # dependency declarations only (no Python package)
├── README.md
├── .gitignore
├── .venv/              # Python virtual environment (gitignored)
├── logs/               # simulation outputs (gitignored)
├── shared.py           # model + embedder factories used by all sims
└── sim_pub.py          # a complete, self-contained simulation
```

That's it. Each `sim_*.py` file imports what it needs (concordia, `shared`,
anything sim-specific), sets up its model and embedder, runs the
simulation, and prints the result.

## Run a simulation

```powershell
python sim_pub.py
python sim_pub.py --provider openrouter
python sim_pub.py --provider anthropic --model claude-sonnet-4-6
```

## Add a new simulation

**Simple sim** (single file): create `sim_<name>.py` at the project root.
Use `sim_pub.py` as a template — copy it, rename, change the premise and
entity definitions, run it.

**Complex sim** (multiple files): create `sim_<name>/` as a directory with
`__init__.py` and however many submodules you need (`premise.py`,
`entities.py`, `components.py`, `data/foo.json`, etc.). Add a small
`__main__.py` or top-level `run.py` so you can launch it with
`python -m sim_<name>` or `python sim_<name>/run.py`.

In either case, the sim should set up its own model and embedder via
`shared.make_model()` and `shared.make_embedder()` so provider switching
stays consistent across the folder.

## About `pyproject.toml`

This project is *not* a Python package — it's a folder of scripts.
`pyproject.toml` is here purely so `pip install -e ".[dev]"` provisions the
venv reproducibly from a single dependency manifest. `packages = []` and
`py-modules = []` under `[tool.setuptools]` tell pip "no code to install,
just process the dependencies."
