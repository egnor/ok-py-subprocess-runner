"""
Test for ok_subprocess_runner.py.
"""

import logging
import ok_subprocess_runner
import os
import pathlib
import pytest
import subprocess


def test_args_prefix():
    sub = ok_subprocess_runner.SubprocessRunner()

    # default args_prefix is empty
    assert sub.args_prefix == []
    assert sub.stdout_lines("echo", "Hello !") == ["Hello !"]

    # set a command prefix
    sub.args_prefix = ["echo", pathlib.Path("prefix")]
    assert sub.stdout_lines("echo", "Hello !") == ["prefix echo Hello !"]


def test_check():
    sub = ok_subprocess_runner.SubprocessRunner()

    # check=True by default
    assert sub.check is True
    sub("true")
    with pytest.raises(subprocess.CalledProcessError):
        sub("false")

    # check=False
    sub.check = False
    sub("true")
    sub("false")

    # override
    sub("true", check=True)
    with pytest.raises(subprocess.CalledProcessError):
        sub("false", check=True)


def test_cwd(tmp_path):
    sub = ok_subprocess_runner.SubprocessRunner()

    # defualt cwd is inherited
    assert sub.cwd == ""
    assert sub.stdout_lines("pwd") == [str(pathlib.Path.cwd())]

    # assign cwd
    sub.cwd = str(tmp_path)  # as str
    assert sub.stdout_lines("pwd") == [str(tmp_path)]

    sub.cwd = tmp_path  # as pathlib.Path
    assert sub.stdout_lines("pwd") == [str(tmp_path)]

    # override entirely
    sub_path = tmp_path / "foo"
    sub_path.mkdir()
    assert sub.stdout_lines("pwd", cwd=sub_path) == [str(sub_path)]


def test_env():
    sub = ok_subprocess_runner.SubprocessRunner()
    save_env = os.environ.copy()

    # default env uses os.environ
    os.environ["TEST_SUBPROCESS_ENVIRON"] = "env value"
    assert sub.env == {}
    vars = sub.stdout_lines("env")
    assert vars == [f"{key}={value}" for key, value in os.environ.items()]

    # env in defaults are added to os.environ
    sub.env = {"TEST_SUBPROCESS_RUNNER": pathlib.Path("added value")}
    vars = sub.stdout_lines("env")
    assert vars == [
        *(f"{key}={value}" for key, value in os.environ.items()),
        "TEST_SUBPROCESS_RUNNER=added value",
    ]

    # env None values are deleted from os.environ
    sub.env = {"TEST_SUBPROCESS_ENVIRON": None}
    vars = sub.stdout_lines("env")
    assert vars == [
        f"{key}={value}"
        for key, value in os.environ.items()
        if key != "TEST_SUBPROCESS_ENVIRON"
    ]

    # override entirely
    vars = sub.stdout_lines("env", env={"TEST_SUBPROCESS_OVERRIDE": "value"})
    assert vars == ["TEST_SUBPROCESS_OVERRIDE=value"]

    os.environ.clear()
    os.environ.update(save_env)


def test_logging_level(caplog):
    caplog.set_level(logging.DEBUG)
    sub = ok_subprocess_runner.SubprocessRunner()

    # default logging at INFO with argument escaping
    assert sub.log_level == logging.INFO
    sub("echo", pathlib.Path("Hello"))
    assert caplog.record_tuples == [("root", logging.INFO, "🐚 echo Hello")]
    caplog.clear()

    # change logging level
    sub.log_level = logging.DEBUG
    sub("echo", "Debug")
    assert caplog.record_tuples == [("root", logging.DEBUG, "🐚 echo Debug")]
    caplog.clear()

    # disable logging
    sub.log_level = logging.NOTSET
    sub("echo", "No log")
    assert caplog.record_tuples == []

    os.environ.clear()


def test_logging_env(caplog):
    caplog.set_level(logging.INFO)
    sub = ok_subprocess_runner.SubprocessRunner()
    save_env = os.environ.copy()

    # environment variables are logged
    sub.env = {"TEST_SUBPROCESS_RUNNER": "added value"}
    sub("echo", "With env")
    assert caplog.record_tuples == [
        (
            "root",
            logging.INFO,
            "🐚 TEST_SUBPROCESS_RUNNER='added value' echo 'With env'",
        )
    ]
    caplog.clear()

    # even logged if specified as an override
    sub("echo", "Override env", env={"TEST_SUBPROCESS_OVERRIDE": "value"})
    assert caplog.record_tuples == [
        (
            "root",
            logging.INFO,
            "🐚 env -i TEST_SUBPROCESS_OVERRIDE=value -- echo 'Override env'",
        )
    ]
    sub.env = {}
    caplog.clear()

    # small additions to long values are represented efficiently
    os.environ["TEST_SUBENV"] = "test-test-long-value"
    sub.env = {"TEST_SUBENV": "foo-test-test-long-value-bar"}
    sub("echo", "With env")
    assert caplog.record_tuples == [
        (
            "root",
            logging.INFO,
            "🐚 TEST_SUBENV=foo-${TEST_SUBENV}-bar echo 'With env'",
        )
    ]
    sub.env = {}
    caplog.clear()

    os.environ.clear()
    os.environ.update(save_env)


def test_logging_cwd(caplog, tmp_path):
    caplog.set_level(logging.INFO)
    sub = ok_subprocess_runner.SubprocessRunner()
    save_cwd = pathlib.Path.cwd()

    # cwd changes are logged
    sub.cwd = tmp_path
    sub("echo", "Hello")
    assert caplog.record_tuples == [
        ("root", logging.INFO, f"🐚 cd {tmp_path} && echo Hello"),
    ]
    caplog.clear()

    os.chdir(tmp_path / "..")
    sub("echo", "Hello")
    assert caplog.record_tuples == [
        ("root", logging.INFO, f"🐚 cd {tmp_path.name} && echo Hello"),
    ]
    caplog.clear()

    os.chdir(tmp_path)
    sub.cwd = pathlib.Path(tmp_path.parent)
    sub("echo", "Hello")
    assert caplog.record_tuples == [
        ("root", logging.INFO, "🐚 cd .. && echo Hello"),
    ]
    caplog.clear()

    os.chdir(save_cwd)


def test_stdout_text():
    sub = ok_subprocess_runner.SubprocessRunner()
    assert sub.stdout_text("echo", "Hello World!") == "Hello World!\n"


def test_stdout_lines():
    sub = ok_subprocess_runner.SubprocessRunner()
    assert sub.stdout_lines("echo", "Hello World!") == ["Hello World!"]
    assert sub.stdout_lines("echo", "Hello\nWorld!") == ["Hello", "World!"]


def test_copy():
    sub = ok_subprocess_runner.SubprocessRunner()
    sub.check = False
    sub.args_prefix = ["args", "prefix"]
    sub.cwd = pathlib.Path("/test")
    sub.env = {"TEST": pathlib.Path("foo/bar")}
    sub.log_level = logging.DEBUG

    copy = sub.copy()
    assert copy.check == sub.check
    assert copy.args_prefix == sub.args_prefix
    assert copy.cwd == sub.cwd
    assert copy.env == sub.env
    assert copy.log_level == sub.log_level

    copy.args_prefix.append("extra")
    copy.env["TEST"] = "new value"
    assert copy.args_prefix != sub.args_prefix
    assert copy.env != sub.env
