"""Collect license files for the runtime dependency graph into a release bundle."""

from __future__ import annotations

import re
import shutil
import sys
from collections import deque
from importlib import metadata
from pathlib import Path
from typing import cast

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
LICENSE_PREFIXES = ("LICENSE", "COPYING", "NOTICE", "AUTHORS")


def direct_runtime_requirements() -> list[Requirement]:
    requirements: list[Requirement] = []
    for raw_line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith(("#", "-r ")):
            requirements.append(Requirement(line))
    return requirements


def runtime_distributions() -> list[metadata.Distribution]:
    installed = {
        canonicalize_name(dist.metadata["Name"]): dist
        for dist in metadata.distributions()
        if dist.metadata.get("Name")
    }
    queue = deque(requirement.name for requirement in direct_runtime_requirements())
    visited: set[str] = set()
    result: list[metadata.Distribution] = []
    environment = cast(dict[str, str], default_environment())

    while queue:
        name = canonicalize_name(queue.popleft())
        if name in visited:
            continue
        visited.add(name)
        dist = installed.get(name)
        if dist is None:
            raise RuntimeError(f"Runtime dependency is not installed: {name}")
        result.append(dist)
        for raw_requirement in dist.requires or ():
            requirement = Requirement(raw_requirement)
            if requirement.marker and not requirement.marker.evaluate(environment):
                continue
            queue.append(requirement.name)
    return sorted(result, key=lambda item: canonicalize_name(item.metadata["Name"]))


def safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-_") or "unknown"


def collect(destination: Path) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    manifest = ["Package\tVersion\tDeclared license\tFiles"]
    copied = 0

    for dist in runtime_distributions():
        name = dist.metadata["Name"]
        version = dist.version
        package_dir = destination / f"{safe_component(name)}-{safe_component(version)}"
        copied_names: list[str] = []
        for index, relative_path in enumerate(dist.files or ()):
            if not relative_path.name.upper().startswith(LICENSE_PREFIXES):
                continue
            source = Path(str(dist.locate_file(relative_path)))
            if not source.is_file():
                continue
            target_name = f"{index:04d}-{safe_component(relative_path.name)}"
            package_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, package_dir / target_name)
            copied_names.append(target_name)
            copied += 1

        declared = dist.metadata.get("License-Expression") or dist.metadata.get("License") or "unspecified"
        declared = " ".join(str(declared).split())
        if len(declared) > 160:
            declared = declared[:157] + "..."
        manifest.append(f"{name}\t{version}\t{declared}\t{', '.join(copied_names) or 'none found'}")

    (destination / "MANIFEST.tsv").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    return copied


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: copy_licenses.py DESTINATION", file=sys.stderr)
        return 2
    destination = Path(sys.argv[1]).resolve()
    count = collect(destination)
    print(f"Collected {count} license/notice files into {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
