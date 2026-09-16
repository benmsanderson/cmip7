"""Grouping CMIP7 experiment_ids into the families we compare.

A model runs either the concentration-driven or the emissions-driven
(``esm-``) version of each experiment, and we treat the two as the same thing
when comparing trajectories. The ``driving`` column records which one it was.

ScenarioMIP experiments are named ``scen7-<name>`` / ``esm-scen7-<name>``,
and their family is ``<name>`` (``vl``, ``h``, ...).
"""

from __future__ import annotations

import re

_FIXED = {
    "historical": "historical",
    "esm-hist": "historical",
    "piControl": "piControl",
    "esm-piControl": "piControl",
}
_SCENARIO = re.compile(r"^(?:esm-)?scen7-(?P<name>[a-z0-9]+)$")


def family(experiment_id: str) -> str | None:
    """Family for an experiment_id, or ``None`` if we don't group it."""
    if experiment_id in _FIXED:
        return _FIXED[experiment_id]
    m = _SCENARIO.match(experiment_id)
    return m["name"] if m else None


def driving(experiment_id: str) -> str:
    return "emissions" if experiment_id.startswith("esm-") else "concentration"
