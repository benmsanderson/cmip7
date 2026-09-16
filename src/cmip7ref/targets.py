"""The approved CMIP7 pull list for the Milan talk.

Members are listed explicitly rather than discovered, because coverage is ragged:
``esm-hist`` r1 has no near-surface CO2 (3-D only) and r4 has CO2 but no ``nbp`` or
``rtmt``. Only r5i1p1f1 has everything and continues into both scenarios.
See docs/data_availability.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MODEL = "UKESM1-3-LL"
SCENARIOS = ("esm-scen7-h", "esm-scen7-vl")
R5 = "r5i1p1f1"


@dataclass(frozen=True)
class Target:
    """One product: a branded variable and the members wanted per experiment."""

    name: str
    branded: str
    variable_id: str
    members: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def experiments(self) -> list[str]:
        return list(self.members)

    @property
    def variants(self) -> list[str]:
        return sorted({v for vs in self.members.values() for v in vs})


CO2 = Target(
    name="co2",
    branded="co2_tavg-h2m-hxy-u",
    variable_id="co2",
    members={
        "esm-hist": ("r4i1p1f1", "r5i1p1f1", "r7i1p1f2", "r8i1p1f2"),
        "esm-scen7-h": (R5,),
        "esm-scen7-vl": (R5,),
    },
)

NBP = Target(
    name="nbp",
    branded="nbp_tavg-u-hxy-lnd",
    variable_id="nbp",
    members={
        "esm-hist": ("r1i1p1f1", "r5i1p1f1", "r7i1p1f2", "r8i1p1f2"),
        "esm-scen7-h": ("r1i1p1f1", R5),
        "esm-scen7-vl": ("r1i1p1f1", R5),
    },
)

RTMT = Target(
    name="rtmt",
    branded="rtmt_tavg-u-hxy-u",
    variable_id="rtmt",
    members={
        "esm-hist": ("r1i1p1f1", "r5i1p1f1", "r7i1p1f2", "r8i1p1f2"),
        "esm-piControl": ("r1i1p1f1",),
    },
)

# fx fields are published only under r5i1p1f1 and are reused across members.
FX_VARIABLES = ("areacella", "sftlf")

TARGETS = {t.name: t for t in (CO2, NBP, RTMT)}


def find(client, target: Target) -> list:
    """Search STAC for exactly the members this target asks for."""
    items = []
    for experiment, variants in target.members.items():
        found = client.search(
            source_id=MODEL,
            branded=target.branded,
            experiment_id=experiment,
            variant_label=list(variants),
        )
        items += found
    return items


def find_fx(client) -> dict[str, list]:
    """The fx fields, from esm-hist r5i1p1f1."""
    return {
        var: client.search(source_id=MODEL, variable_id=var, experiment_id="esm-hist", variant_label=R5)
        for var in FX_VARIABLES
    }


def expected(target: Target) -> list[tuple[str, str]]:
    """``(experiment, variant)`` pairs this target expects, for the coverage check."""
    return [(exp, v) for exp, vs in target.members.items() for v in vs]
