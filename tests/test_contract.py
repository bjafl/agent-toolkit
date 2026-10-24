"""Every tool must be registered as a command, documented as a skill and have help examples."""

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())
TOOLS = sorted(PYPROJECT["project"]["scripts"])


@pytest.mark.parametrize("tool", TOOLS)
def test_tool_has_skill(tool):
    skill = ROOT / "skills" / tool / "SKILL.md"
    assert skill.is_file(), f"missing {skill.relative_to(ROOT)}"
    front = re.match(r"---\n(.*?)\n---\n", skill.read_text(), re.S)
    assert front, "SKILL.md needs YAML frontmatter"
    assert f"name: {tool}\n" in front.group(1) + "\n"
    assert "description: " in front.group(1)


@pytest.mark.parametrize("tool", TOOLS)
def test_help_has_examples(tool):
    module = PYPROJECT["project"]["scripts"][tool].split(":")[0]
    out = subprocess.run(
        [sys.executable, "-m", module, "--help"], capture_output=True, text=True, check=True
    ).stdout
    assert "examples:" in out


def test_plugin_version_matches_package():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["version"] == PYPROJECT["project"]["version"]
