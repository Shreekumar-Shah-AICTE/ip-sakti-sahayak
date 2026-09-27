"""Repository hygiene: secrets ignored, no forbidden claims in shipped text."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {".md", ".py", ".ts", ".tsx", ".json", ".html", ".yaml", ".yml", ".txt"}
SKIP_DIRS = {"node_modules", ".git", "dist", ".venv", "__pycache__"}

# Phrases assembled at runtime so this file does not match itself.
FORBIDDEN = [
    " ".join(["substitute", "for", "a", "lawyer"]),
    " ".join(["replaces", "a", "lawyer"]),
    " ".join(["we", "query", "tkdl"]),
]


def _files():
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in TEXT_SUFFIXES and not SKIP_DIRS & set(p.parts):
            yield p


def test_env_is_gitignored():
    r = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=ROOT)
    assert r.returncode == 0, ".env must be listed in .gitignore"


def test_no_forbidden_claims():
    hits = []
    for p in _files():
        text = p.read_text(encoding="utf-8", errors="ignore").lower()
        hits += [f"{p.relative_to(ROOT)}: {phrase}" for phrase in FORBIDDEN if phrase in text]
    assert not hits, hits


def test_run_sh_is_executable_in_git():
    """`./run.sh` is the evaluator's first command; git must store it as 100755."""
    out = subprocess.run(
        ["git", "ls-files", "-s", "run.sh"], capture_output=True, text=True, cwd=ROOT
    ).stdout
    assert not out or out.startswith("100755")
