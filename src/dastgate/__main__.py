"""Console entry point — Phase 0 stub.

Resolves the ``dastgate`` console script declared in ``pyproject.toml`` so the
package installs cleanly. The tool is not implemented yet — see ``docs/DESIGN.md``
(§5.1 for the intended ``dastgate run --target <name> | --all`` CLI).
"""

from __future__ import annotations

import sys


def main() -> int:
    sys.stderr.write(
        "dastgate is a Phase 0 scaffold and is not implemented yet.\n"
        "See docs/DESIGN.md for the design and the phased build plan.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
