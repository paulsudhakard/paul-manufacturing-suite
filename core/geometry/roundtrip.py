"""TDD §5.4 round-trip contract: NeutralToShape(ShapeToNeutral(s)) must
differ from `s` by no more than an epsilon (default 0.001mm), with
subpath count/closedness unchanged.

Core-side, we can only compare two NeutralGeometry values for now — the
actual ShapeToNeutral/NeutralToShape conversion lives on the Adapter
side (CorelDRAW COM), which requires real CorelDRAW to exercise (not
available in this environment). `assert_round_trip` is what a real
Adapter round-trip test (or this chunk's simulated one) checks its
result against.
"""
from __future__ import annotations

import math

from core.geometry.models import NeutralGeometry

DEFAULT_EPSILON_MM = 0.001


class RoundTripViolation(Exception):
    pass


def assert_round_trip(
    original: NeutralGeometry,
    restored: NeutralGeometry,
    epsilon: float = DEFAULT_EPSILON_MM,
) -> None:
    if len(original.layers) != len(restored.layers):
        raise RoundTripViolation(
            f"layer count changed: {len(original.layers)} -> {len(restored.layers)}"
        )
    for layer_index, (orig_layer, new_layer) in enumerate(zip(original.layers, restored.layers)):
        if len(orig_layer.objects) != len(new_layer.objects):
            raise RoundTripViolation(f"layer[{layer_index}] object count changed")
        for obj_index, (orig_obj, new_obj) in enumerate(
            zip(orig_layer.objects, new_layer.objects)
        ):
            if len(orig_obj.subpaths) != len(new_obj.subpaths):
                raise RoundTripViolation(
                    f"layer[{layer_index}].object[{obj_index}] subpath count changed"
                )
            for sp_index, (orig_sp, new_sp) in enumerate(
                zip(orig_obj.subpaths, new_obj.subpaths)
            ):
                if orig_sp.closed != new_sp.closed:
                    raise RoundTripViolation(
                        f"layer[{layer_index}].object[{obj_index}].subpath[{sp_index}] "
                        f"closedness changed"
                    )
                if len(orig_sp.nodes) != len(new_sp.nodes):
                    raise RoundTripViolation(
                        f"layer[{layer_index}].object[{obj_index}].subpath[{sp_index}] "
                        f"node count changed"
                    )
                for n_index, (orig_n, new_n) in enumerate(zip(orig_sp.nodes, new_sp.nodes)):
                    dist = math.hypot(orig_n.x - new_n.x, orig_n.y - new_n.y)
                    if dist > epsilon:
                        raise RoundTripViolation(
                            f"layer[{layer_index}].object[{obj_index}].subpath[{sp_index}]"
                            f".node[{n_index}] moved {dist:.6f}mm (epsilon {epsilon}mm)"
                        )
