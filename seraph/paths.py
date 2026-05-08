"""
seraph.paths — Smart Path Handling
====================================
OS-agnostic paths that understand where they're running.
No more wrong slashes, no more os.path.join hell, no more "relative to what?".
"""

from __future__ import annotations

import configparser
import inspect
import json
import pathlib
from typing import Any, List, Union

PathLike = Union[str, pathlib.Path, "SmartPath"]


def _sp(p: pathlib.Path) -> "SmartPath":
    inst = SmartPath.__new__(SmartPath)
    inst._path = p
    return inst


class SmartPath:
    """
    A path that just works — on Windows, Linux, and macOS.

    Key features
    ------------
    - / operator joins paths (like pathlib), works on all OSes
    - .read() / .write() / .read_json() / .write_json() built-in
    - .read_config() for INI/cfg files
    - .read_env() reads a .env file into a dict
    - .ls() lists directory contents as SmartPaths
    - Auto-creates parent directories on write
    - Fully compatible with builtins that expect os.PathLike

    Examples
    --------
        base = here()                           # script's own directory
        cfg  = base / "config" / "app.json"    # cross-OS join
        data = cfg.read_json()

        (base / "output" / "result.txt").write("done")   # parents auto-created

        for f in here().ls("*.py"):
            print(f.name)
    """

    def __init__(self, path: PathLike) -> None:
        if isinstance(path, SmartPath):
            self._path = path._path
        else:
            self._path = pathlib.Path(path)

    # ── Path joining ──────────────────────────────────────────────────────────

    def __truediv__(self, other: Union[str, "SmartPath"]) -> "SmartPath":
        other_p = other._path if isinstance(other, SmartPath) else other
        return _sp(self._path / other_p)

    def __rtruediv__(self, other: str) -> "SmartPath":
        return _sp(pathlib.Path(other) / self._path)

    # ── OS-path protocol ──────────────────────────────────────────────────────

    def __fspath__(self) -> str:
        return str(self._path)

    def __str__(self) -> str:
        return str(self._path)

    def __repr__(self) -> str:
        return f"SmartPath({str(self._path)!r})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SmartPath):
            return self._path == other._path
        return self._path == pathlib.Path(other)

    def __hash__(self) -> int:
        return hash(self._path)

    # ── Metadata ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._path.name

    @property
    def stem(self) -> str:
        return self._path.stem

    @property
    def suffix(self) -> str:
        return self._path.suffix

    @property
    def parent(self) -> "SmartPath":
        return _sp(self._path.parent)

    @property
    def absolute(self) -> "SmartPath":
        return _sp(self._path.resolve())

    def exists(self) -> bool:
        return self._path.exists()

    def is_file(self) -> bool:
        return self._path.is_file()

    def is_dir(self) -> bool:
        return self._path.is_dir()

    @property
    def size(self) -> int:
        return self._path.stat().st_size

    # ── Reading ───────────────────────────────────────────────────────────────

    def read(self, encoding: str = "utf-8") -> str:
        return self._path.read_text(encoding=encoding)

    def read_bytes(self) -> bytes:
        return self._path.read_bytes()

    def read_lines(self, encoding: str = "utf-8", strip: bool = True) -> List[str]:
        lines = self.read(encoding=encoding).splitlines()
        return [ln.strip() for ln in lines] if strip else lines

    def read_json(self, encoding: str = "utf-8") -> Any:
        try:
            return json.loads(self._path.read_text(encoding=encoding))
        except json.JSONDecodeError as e:
            raise ValueError(f"[Seraph] Invalid JSON in {self}: {e}") from e

    def read_config(self) -> configparser.ConfigParser:
        parser = configparser.ConfigParser()
        parser.read(str(self._path), encoding="utf-8")
        return parser

    def read_env(self) -> dict:
        env: dict = {}
        if not self._path.exists():
            return env
        for line in self.read_lines():
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip().strip('"').strip("'")
        return env

    # ── Writing ───────────────────────────────────────────────────────────────

    def _ensure_parents(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, content: str, encoding: str = "utf-8") -> "SmartPath":
        self._ensure_parents()
        self._path.write_text(content, encoding=encoding)
        return self

    def write_bytes(self, content: bytes) -> "SmartPath":
        self._ensure_parents()
        self._path.write_bytes(content)
        return self

    def write_json(self, data: Any, indent: int = 2,
                   ensure_ascii: bool = False, encoding: str = "utf-8") -> "SmartPath":
        self._ensure_parents()
        self._path.write_text(
            json.dumps(data, indent=indent, ensure_ascii=ensure_ascii),
            encoding=encoding,
        )
        return self

    def append(self, content: str, encoding: str = "utf-8") -> "SmartPath":
        self._ensure_parents()
        with open(self._path, "a", encoding=encoding) as f:
            f.write(content)
        return self

    # ── Directory operations ──────────────────────────────────────────────────

    def ls(self, pattern: str = "*") -> List["SmartPath"]:
        return [_sp(p) for p in sorted(self._path.glob(pattern))]

    def ls_recursive(self, pattern: str = "**/*") -> List["SmartPath"]:
        return [_sp(p) for p in sorted(self._path.glob(pattern))]

    def mkdir(self, exist_ok: bool = True) -> "SmartPath":
        self._path.mkdir(parents=True, exist_ok=exist_ok)
        return self

    def delete(self) -> None:
        self._path.unlink(missing_ok=True)

    def with_name(self, name: str) -> "SmartPath":
        return _sp(self._path.with_name(name))

    def with_suffix(self, suffix: str) -> "SmartPath":
        return _sp(self._path.with_suffix(suffix))

    def open(self, mode: str = "r", encoding: str = "utf-8", **kwargs):
        self._ensure_parents()
        return open(self._path, mode=mode, encoding=encoding, **kwargs)

    @classmethod
    def home(cls) -> "SmartPath":
        return _sp(pathlib.Path.home())

    @classmethod
    def cwd(cls) -> "SmartPath":
        return _sp(pathlib.Path.cwd())

    @classmethod
    def temp(cls) -> "SmartPath":
        import tempfile
        return _sp(pathlib.Path(tempfile.gettempdir()))


def here(_depth: int = 1) -> SmartPath:
    """
    Return a SmartPath pointing to the directory of the calling script.
    Always correct regardless of the terminal's cwd.

        config = here() / "config.json"
    """
    frame = inspect.stack()[_depth]
    caller_file = frame[1]
    if caller_file.startswith("<"):
        return _sp(pathlib.Path.cwd())
    return _sp(pathlib.Path(caller_file).resolve().parent)
