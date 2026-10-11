"""The packs: businesses on the framework. River Plumbing's Appointment Line comes first:
it is the Knowledge Line the book walks through, and the claims line is the showcase."""
from __future__ import annotations


def all_packs():
    from .claims.pack import ClaimsPack
    from .river_plumbing.pack import RiverPlumbingPack
    return [RiverPlumbingPack(), ClaimsPack()]
