"""Bridge between the Geometry Engine's native model (core.engines.geometry
.model) and the wire-format NeutralGeometry (core.geometry — TDD §5.2).

NeutralGeometry nodes only support "line" and "curve" (cubic Bezier via
per-node control_in/control_out handles) — no native arc representation.
Exporting an ArcSegment therefore approximates it with Beziers
(core.engines.geometry.flatten.arc_to_beziers) — lossy but tolerance-
bounded (~0.02% max radial error per <=90-degree span), not exact. This
is the one direction where round-tripping through NeutralGeometry is
not bit-for-bit identical for arc-containing geometry; Line/Bezier
geometry round-trips exactly.
"""
from __future__ import annotations

from core.engines.geometry.flatten import arc_to_beziers
from core.engines.geometry.model import (
    ArcSegment,
    BezierSegment,
    CompoundPath,
    LineSegment,
    Path,
    Point,
    Segment,
    Shape,
    as_compound,
)
from core.geometry.models import (
    BoundingBox as NGBoundingBox,
)
from core.geometry.models import (
    Fill as NGFill,
)
from core.geometry.models import (
    GeometryMetadata as NGMetadata,
)
from core.geometry.models import (
    GeometryObject as NGObject,
)
from core.geometry.models import (
    Layer as NGLayer,
)
from core.geometry.models import (
    NeutralGeometry,
)
from core.geometry.models import (
    Node as NGNode,
)
from core.geometry.models import (
    Point as NGPoint,
)
from core.geometry.models import (
    Subpath as NGSubpath,
)


def _flatten_arcs(segments: tuple[Segment, ...]) -> list[Segment]:
    expanded: list[Segment] = []
    for s in segments:
        if isinstance(s, ArcSegment):
            expanded.extend(arc_to_beziers(s))
        else:
            expanded.append(s)
    return expanded


def path_to_subpath(path: Path) -> NGSubpath:
    segments = _flatten_arcs(path.segments)
    if not segments:
        return NGSubpath(closed=path.closed, nodes=())

    # One "start" node per segment (segment i's start == segment i-1's end
    # for a well-formed contiguous path, so this never double-counts an
    # interior point).
    start_nodes: list[NGNode] = []
    for seg in segments:
        if isinstance(seg, LineSegment):
            start_nodes.append(NGNode(x=seg.start.x, y=seg.start.y, node_type="line"))
        elif isinstance(seg, BezierSegment):
            start_nodes.append(
                NGNode(
                    x=seg.start.x,
                    y=seg.start.y,
                    node_type="curve",
                    control_out=NGPoint(seg.control1.x, seg.control1.y),
                )
            )
        else:
            raise TypeError(f"Unexpected segment after arc flattening: {type(seg)}")

    if path.closed:
        # The last segment's end coincides with the first node (closed=True
        # makes that wraparound implicit) — no extra node, just attach
        # control_in from the last segment's control2 onto node[0] if Bezier.
        nodes = start_nodes
        last = segments[-1]
        if isinstance(last, BezierSegment):
            nodes[0] = NGNode(
                x=nodes[0].x,
                y=nodes[0].y,
                node_type=nodes[0].node_type,
                control_in=NGPoint(last.control2.x, last.control2.y),
                control_out=nodes[0].control_out,
            )
    else:
        # Open path: one real trailing node for the final segment's end point.
        last = segments[-1]
        end_node = NGNode(x=last.end.x, y=last.end.y, node_type="line")
        nodes = start_nodes + [end_node]

    # Attach control_in for every *interior* node that follows a Bezier
    # segment (the closed-path wraparound case above is handled separately).
    fixed_nodes = [nodes[0]]
    for i, seg in enumerate(segments):
        if path.closed and i == len(segments) - 1:
            break  # wraparound control_in already applied to nodes[0] above
        next_node = nodes[i + 1]
        if isinstance(seg, BezierSegment):
            next_node = NGNode(
                x=next_node.x,
                y=next_node.y,
                node_type=next_node.node_type,
                control_in=NGPoint(seg.control2.x, seg.control2.y),
                control_out=next_node.control_out,
            )
        fixed_nodes.append(next_node)

    return NGSubpath(closed=path.closed, nodes=tuple(fixed_nodes))


def shape_to_neutral(
    shape: Shape, source_adapter: str = "geometry_engine", layer_role: str = "original"
) -> NeutralGeometry:
    from core.engines.geometry.bounds import bounding_box

    compound = as_compound(shape)
    bbox = bounding_box(shape)
    objects = tuple(
        NGObject(object_id=f"obj-{i}", subpaths=(path_to_subpath(p),), fill=NGFill(), stroke=None)
        for i, p in enumerate(compound.paths)
        if p.segments
    )
    return NeutralGeometry(
        units="mm",
        bounding_box=NGBoundingBox(bbox.min_x, bbox.min_y, bbox.width, bbox.height),
        layers=(NGLayer(layer_role, objects),),
        metadata=NGMetadata(source_adapter=source_adapter),
    )


def subpath_to_path(subpath: NGSubpath) -> Path:
    ng_nodes = list(subpath.nodes)
    if not ng_nodes:
        return Path((), closed=subpath.closed)

    n = len(ng_nodes)
    count = n if subpath.closed else n - 1
    segments: list[Segment] = []
    for i in range(count):
        node = ng_nodes[i]
        next_node = ng_nodes[(i + 1) % n]
        start = Point(node.x, node.y)
        end = Point(next_node.x, next_node.y)
        if node.control_out is not None or next_node.control_in is not None:
            c1 = (
                Point(node.control_out.x, node.control_out.y)
                if node.control_out is not None
                else start
            )
            c2 = (
                Point(next_node.control_in.x, next_node.control_in.y)
                if next_node.control_in is not None
                else end
            )
            segments.append(BezierSegment(start, c1, c2, end))
        else:
            segments.append(LineSegment(start, end))
    return Path(tuple(segments), closed=subpath.closed)


def neutral_to_shape(geometry: NeutralGeometry) -> CompoundPath:
    paths: list[Path] = []
    for layer in geometry.layers:
        for obj in layer.objects:
            for subpath in obj.subpaths:
                paths.append(subpath_to_path(subpath))
    return CompoundPath(tuple(paths))
