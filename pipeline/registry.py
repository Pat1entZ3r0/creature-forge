"""Archetype registry. Add new archetypes here; the orchestrator picks by name."""

from __future__ import annotations

from archetypes.arachnid import Arachnid

ARCHETYPES = {
    "arachnid": Arachnid,
}


def get_archetype(name: str):
    if name not in ARCHETYPES:
        raise KeyError(f"unknown archetype {name!r}; known: {sorted(ARCHETYPES)}")
    return ARCHETYPES[name]()
