"""
Minor utilities and wrappers for the Python subprocess library
"""

import dataclasses
import logging
import os
import shlex
import subprocess


@dataclasses.dataclass
class SubprocessRunner:
    """Wrapper for subprocess.run, plus some convenience methods.

    sub = SubprocessRunner()
    sub("echo", "Hello", "World")
    """

    args_prefix: list = dataclasses.field(default_factory=list)
    """Arguments (including command) to prepend to args for run methods."""

    check: bool = True
    """Default subprocess.run setting, True to raise on non-zero exit codes."""

    cwd: str = ""
    """Default directory for subprocess."""

    env: dict = dataclasses.field(default_factory=dict)
    """Default environment variables **added** to os.environ for subprocess."""

    log_level: int = logging.INFO
    """Logging level to print commands, or logging.NOTSET to disable."""

    def __call__(self, *args, **kw):
        """Wraps subprocess.run (with args directly listed), logging the
        command (per log_level) and applying defaults from this object."""

        cwd = _path_str(self.cwd) if self.cwd else None

        env = None
        if self.env:
            env = {**os.environ, **self.env}
            env = {k: _path_str(v) for k, v in env.items() if v is not None}

        run_args = [_path_str(a) for a in [*self.args_prefix, *args]]
        run_kw = {"check": self.check, "cwd": cwd, "env": env, **kw}

        if self.log_level and self.log_level > logging.NOTSET:
            _log_command(self.log_level, run_args, run_kw)

        return subprocess.run(run_args, **run_kw)

    def stdout_text(self, *args, **kw):
        """Like run, but captures and directly returns stdout text."""

        kw = {"stdout": subprocess.PIPE, "text": True, **kw}
        return self(*args, **kw).stdout

    def stdout_lines(self, *args, **kw):
        """Like stdout_text, but splits the text into lines."""

        return self.stdout_text(*args, **kw).splitlines()

    def copy(self):
        """Returns a copy of this object with the same defaults."""

        return dataclasses.replace(
            self, args_prefix=self.args_prefix.copy(), env=self.env.copy()
        )


def _path_str(path_or_str: os.PathLike | str) -> str:
    if isinstance(path_or_str, str):
        return path_or_str
    if isinstance(path_or_str, os.PathLike):
        return str(path_or_str)
    raise TypeError(f"Expected str or os.PathLike, got {path_or_str!r}")


def _log_command(log_level, args, kw):
    cd_parts = []
    if new_cwd := kw.get("cwd"):
        old_path = os.path.realpath(os.getcwd())
        new_path = os.path.realpath(new_cwd)
        if new_path != old_path:
            try:
                rel_path = os.path.relpath(new_path, old_path)
                if len(rel_path) < len(new_path):
                    new_path = rel_path
            except ValueError:
                pass  # different drives on Windows
            cd_parts = ["cd", shlex.quote(str(new_path)), "&&"]

    env_parts = []
    if new_env := kw.get("env"):
        old_env = os.environ
        repeats, updates = [], []
        for k, new_v in new_env.items():
            old_v = old_env.get(k)
            v_quoted = shlex.quote(new_v) if new_v else ""
            v_parts = new_v.split(old_v) if old_v else [new_v]
            if len(v_parts) > 1:
                v_parts_quoted = [shlex.quote(p) if p else "" for p in v_parts]
                v_spliced = f"${{{k}}}".join(v_parts_quoted)
                if len(v_spliced) < len(v_quoted):
                    v_quoted = v_spliced

            (repeats if old_v == new_v else updates).append(f"{k}={v_quoted}")

        def parts_len(parts):
            return sum(len(p) for p in parts)

        env_parts = updates
        if del_keys := old_env.keys() - new_env.keys():
            env_parts = ["env", *(f"-u{k}" for k in del_keys), *updates, "--"]
            env_reset_parts = ["env -i", *repeats, *updates, "--"]
            if parts_len(env_reset_parts) < parts_len(env_parts):
                env_parts = env_reset_parts

    command_text = " ".join(shlex.quote(arg) for arg in args)
    log_parts = [*cd_parts, *env_parts, command_text]
    logging.log(log_level, "🐚 %s", " ".join(log_parts))
