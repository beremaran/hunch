"""Invariant 3: there is no write path to core/ or to .env anywhere in src/.

.env holds secrets and settings, so it is protected the same way as core/.

Three layers:
1. Static AST scan of src/: only the read-only loader may name core paths, and it may not call
   any file-writing API.
2. Tripwire: only allowlisted modules may write files at all. Each of them must check its target
   against core/ at write time (e.g. AmendmentQueue). Adding a new file writer to src/ fails this
   test until it is reviewed and allowlisted.
3. Runtime guard: every file-write primitive is patched; any write under core/ while the loader
   and the amendment queue run fails the test.
"""

from __future__ import annotations

import ast
import builtins
import io
import os
from pathlib import Path

import pytest

from hunch.values.amendments import AmendmentKind, AmendmentProposal, AmendmentQueue
from hunch.values.core import load_core_values, require_core_values

SRC = Path(__file__).resolve().parents[1] / "src" / "hunch"
REPO_ROOT = SRC.parents[1]
CORE_PATH_MODULES = {"values/core.py"}  # the read-only loader
ENV_PATH_MODULES: set[str] = set()  # nobody names .env yet; a future read-only loader goes here
FILE_WRITER_MODULES = {"values/amendments.py"}  # each re-checks its target against core/

_PATH_WRITE_METHODS = {
    "write_text", "write_bytes", "touch", "mkdir", "unlink", "rmdir", "rename", "replace",
    "chmod", "symlink_to", "hardlink_to",
}  # fmt: skip
_MODULE_WRITE_FUNCS = {
    "os": {"remove", "unlink", "rename", "replace", "renames", "makedirs", "mkdir", "rmdir",
           "chmod", "truncate", "removedirs", "symlink", "link", "write", "utime", "system",
           "popen", "startfile"},
    "shutil": {"copy", "copy2", "copyfile", "copytree", "move", "rmtree", "copymode",
               "copystat"},
    "sqlite3": {"connect"},
    "tempfile": {"NamedTemporaryFile", "mkstemp", "mkdtemp", "TemporaryFile"},
    "subprocess": {"run", "call", "check_call", "check_output", "Popen"},
    "logging": {"FileHandler", "basicConfig"},
    "handlers": {"RotatingFileHandler", "TimedRotatingFileHandler", "WatchedFileHandler"},
    "dotenv": {"set_key", "unset_key"},  # python-dotenv's .env writers
}  # fmt: skip
_ALL_WRITE_NAMES = _PATH_WRITE_METHODS | set().union(*_MODULE_WRITE_FUNCS.values())


def _mode_arg(call: ast.Call, position: int) -> str | None:
    for kw in call.keywords:
        if kw.arg == "mode":
            return kw.value.value if isinstance(kw.value, ast.Constant) else "?"
    if len(call.args) > position:
        node = call.args[position]
        return node.value if isinstance(node, ast.Constant) else "?"
    return "r"


def _is_write_mode(mode: object) -> bool:
    return not isinstance(mode, str) or mode == "?" or any(c in mode for c in "wax+")


def _import_aliases(tree: ast.AST) -> tuple[dict[str, str], dict[str, str]]:
    """local module alias -> module, and local function name -> 'module.func' for write funcs."""
    modules: dict[str, str] = {}
    funcs: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                root = a.name.split(".")[-1]
                modules[a.asname or a.name.split(".")[0]] = root if a.asname else a.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module.split(".")[-1]
            for a in node.names:
                if a.name in _MODULE_WRITE_FUNCS.get(mod, ()):
                    funcs[a.asname or a.name] = f"{mod}.{a.name}"
                elif a.name in _MODULE_WRITE_FUNCS:  # from logging import handlers
                    modules[a.asname or a.name] = a.name
    return modules, funcs


def write_calls(tree: ast.AST) -> list[str]:
    modules, funcs = _import_aliases(tree)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        line = node.lineno
        if isinstance(f, ast.Name):
            if f.id in ("open", "io.open") and _is_write_mode(_mode_arg(node, 1)):
                found.append(f"open() line {line}")
            elif f.id in funcs:
                found.append(f"{funcs[f.id]}() line {line}")
            elif f.id in ("getattr", "setattr", "__import__", "exec", "eval"):
                args = [a.value for a in node.args if isinstance(a, ast.Constant)]
                if f.id != "getattr" or any(a in _ALL_WRITE_NAMES for a in args):
                    found.append(f"{f.id}() line {line}")
        elif isinstance(f, ast.Attribute):
            owner = modules.get(f.value.id, f.value.id) if isinstance(f.value, ast.Name) else None
            if f.attr == "open" and owner != "os" and _is_write_mode(_mode_arg(node, 0)):
                found.append(f".open() line {line}")
            elif f.attr == "open" and owner == "os":
                found.append(f"os.open() line {line}")
            elif f.attr in _PATH_WRITE_METHODS:
                found.append(f".{f.attr}() line {line}")
            elif owner and f.attr in _MODULE_WRITE_FUNCS.get(owner, ()):
                found.append(f"{owner}.{f.attr}() line {line}")
    return found


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _names_core(value: str) -> bool:
    v = value.replace("\\", "/").casefold()
    parts = [p for p in v.split("/") if p not in ("", ".", "..")]
    return "core" in parts or "values.yaml" in v or "values.pub" in v or v.endswith(".sig")


def core_path_refs(tree: ast.AST) -> list[str]:
    """String literals in code (not docstrings) that name core/ or its files."""
    docstrings = _docstring_nodes(tree)
    return [
        repr(node.value)
        for node in ast.walk(tree)
        if id(node) not in docstrings
        and isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _names_core(node.value)
    ]


def _names_env(value: str) -> bool:
    return ".env" in value.replace("\\", "/").casefold().split("/")


def env_path_refs(tree: ast.AST) -> list[str]:
    """String literals in code (not docstrings) that name the .env file."""
    docstrings = _docstring_nodes(tree)
    return [
        repr(node.value)
        for node in ast.walk(tree)
        if id(node) not in docstrings
        and isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _names_env(node.value)
    ]


def _src_modules() -> list[tuple[str, ast.AST]]:
    out = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        out.append((rel, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))))
    return out


# --- the scanner itself ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code",
    [
        "open(p, 'w')",
        "open(p, mode='ab')",
        "open(file=p, mode='w')",
        "open(p, m)",
        "Path(p).write_text('x')",
        "os.replace(a, b)",
        "import os as o\no.remove(p)",
        "from os import remove\nremove(p)",
        "from shutil import move as mv\nmv(a, b)",
        "p.open('x')",
        "os.open(p, flags)",
        "shutil.copyfile(a, b)",
        "getattr(p, 'write_bytes')(b'x')",
        "sqlite3.connect(db)",
        "logging.FileHandler(p)",
        "from logging import handlers\nhandlers.RotatingFileHandler(p)",
        "subprocess.run(['cmd'])",
        "tempfile.mkstemp()",
        "from dotenv import set_key\nset_key('.env', 'K', 'v')",
        "dotenv.unset_key(p, 'K')",
    ],
)
def test_scanner_detects_writes(code: str) -> None:
    assert write_calls(ast.parse(code)), code


@pytest.mark.parametrize("code", ["open(p)", "open(p, 'rb')", "p.read_bytes()", "p.open()"])
def test_scanner_ignores_reads(code: str) -> None:
    assert write_calls(ast.parse(code)) == []


@pytest.mark.parametrize(
    "literal", ["core", "core/values.yaml", "Core/Values.YAML", "./core/x", "..\\core\\x", "x.sig"]
)
def test_core_path_matching_is_normalized(literal: str) -> None:
    assert core_path_refs(ast.parse(f"x = {literal!r}"))


def test_core_word_in_prose_is_not_a_path() -> None:
    assert core_path_refs(ast.parse("x = 'the core values dir'")) == []


@pytest.mark.parametrize("literal", [".env", "C:\\hunch\\.env", "./.env", "../.ENV"])
def test_env_path_matching(literal: str) -> None:
    assert env_path_refs(ast.parse(f"x = {literal!r}"))


@pytest.mark.parametrize("literal", [".env.example", "the .env file holds secrets", "environ"])
def test_env_matching_ignores_other_names(literal: str) -> None:
    assert env_path_refs(ast.parse(f"x = {literal!r}")) == []


# --- the invariant -----------------------------------------------------------------------------


def test_only_the_loader_names_core_paths() -> None:
    offenders = {rel for rel, tree in _src_modules() if core_path_refs(tree)}
    assert offenders <= CORE_PATH_MODULES, offenders


def test_the_loader_never_writes_files() -> None:
    for rel, tree in _src_modules():
        if rel in CORE_PATH_MODULES or core_path_refs(tree):
            assert write_calls(tree) == [], f"{rel} names core paths and writes files"


def test_only_reviewed_modules_name_dotenv_and_none_of_them_write() -> None:
    for rel, tree in _src_modules():
        if env_path_refs(tree):
            assert rel in ENV_PATH_MODULES, f"{rel} names .env: {env_path_refs(tree)}"
            assert write_calls(tree) == [], f"{rel} names .env and writes files"


def test_only_reviewed_modules_write_files() -> None:
    """Tripwire: a new file writer in src/ must be reviewed for a write-time core/ check."""
    writers = {rel: write_calls(tree) for rel, tree in _src_modules() if write_calls(tree)}
    assert set(writers) <= FILE_WRITER_MODULES, writers


# --- runtime guard -----------------------------------------------------------------------------


@pytest.fixture
def core_write_guard(monkeypatch: pytest.MonkeyPatch, core_values_file: Path):
    def norm(p: Path) -> Path:
        return Path(os.path.normcase(p.resolve()))

    protected_dirs = [norm(core_values_file.parent)]
    # The real repo .env and a decoy next to the test's core/ dir.
    protected_files = [norm(REPO_ROOT / ".env"), norm(core_values_file.parent.parent / ".env")]
    hits: list[str] = []

    def in_core(path: object) -> bool:
        if isinstance(path, int):  # file descriptor
            return False
        try:
            p = norm(Path(os.fsdecode(path)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
        return p in protected_files or any(d == p or d in p.parents for d in protected_dirs)

    def guard(name, real, path_params: tuple[str, ...], is_write=lambda *a, **k: True):
        def wrapper(*args, **kwargs):
            paths = list(args[: len(path_params)]) + [kwargs[k] for k in path_params if k in kwargs]
            if is_write(*args, **kwargs) and any(in_core(p) for p in paths):
                hits.append(f"{name}({paths})")
            return real(*args, **kwargs)

        return wrapper

    def open_writes(*args, **kwargs) -> bool:
        mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
        return any(c in mode for c in "wax+")

    def os_open_writes(*args, **kwargs) -> bool:
        flags = kwargs.get("flags", args[1] if len(args) > 1 else 0)
        return bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))

    monkeypatch.setattr(builtins, "open", guard("open", builtins.open, ("file",), open_writes))
    monkeypatch.setattr(io, "open", guard("io.open", io.open, ("file",), open_writes))
    monkeypatch.setattr(os, "open", guard("os.open", os.open, ("path",), os_open_writes))
    for name in ("mkdir", "makedirs", "remove", "unlink", "rmdir", "chmod", "truncate", "utime"):
        monkeypatch.setattr(os, name, guard(f"os.{name}", getattr(os, name), ("path",)))
    for name in ("rename", "replace", "symlink", "link"):
        monkeypatch.setattr(os, name, guard(f"os.{name}", getattr(os, name), ("src", "dst")))
    return hits


def test_guard_catches_writes_into_core(core_values_file: Path, core_write_guard) -> None:
    core = core_values_file.parent
    (core / "x.txt").write_text("x")
    with open(file=core / "y.txt", mode="w") as f:
        f.write("y")
    os.replace(core / "y.txt", core / "z.txt")
    assert len(core_write_guard) == 3, core_write_guard


def test_guard_catches_writes_to_dotenv(core_values_file: Path, core_write_guard) -> None:
    decoy = core_values_file.parent.parent / ".env"
    decoy.write_text("TELEGRAM_ADMIN_USER_ID=attacker\n")
    with open(decoy, "a") as f:
        f.write("X=1\n")
    assert len(core_write_guard) == 2, core_write_guard


def test_runtime_paths_never_write_to_core(
    core_values_file: Path, core_write_guard, tmp_path: Path
) -> None:
    from hunch.config import load_config

    load_config()
    load_core_values(core_values_file)
    require_core_values(core_values_file)
    queue = AmendmentQueue(tmp_path / "data" / "amendments", core_dir=core_values_file.parent)
    queue.submit(
        AmendmentProposal.create(
            kind=AmendmentKind.ADD,
            value_id="kindness",
            rationale="test",
            proposed_statement="The AI is kind.",
        )
    )
    assert len(queue.pending()) == 1
    assert core_write_guard == []
