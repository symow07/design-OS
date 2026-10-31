"""Fit observed motif pixels to supported straight, physical-width vector lines.

This module neither changes picture pixels nor invokes a provider/native app.
The caller owns the motif mask and must exclude all lettering and logos.
"""
import hashlib
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import cv2
import fitz
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from .round_files_refinement_v2 import skeleton


class WidthEvidenceError(ValueError):
    """A reviewable evidence failure, including its original sampling context."""
    def __init__(self, message, diagnostic):
        super().__init__(message)
        self.diagnostic = diagnostic


def _width_failure(message, start, end, mask, samples, reason):
    accepted = [row for row in samples if 'accepted' in row and row['accepted']]
    return WidthEvidenceError(message, {
        'schema': 'line_width_evidence_error/1', 'stage': 'cross_sections', 'reason': reason,
        'endpoints_mm': [start.tolist(), end.tolist()],
        'reference_size_px': [mask.shape[1], mask.shape[0]],
        'accepted_samples': len(accepted),
        'independent_original_station_cells': len({tuple(row['original_station_cell']) for row in accepted}),
        'minimum_independent_station_cells': 3, 'samples': samples})


DEFAULT_FOIL_WIDTH_MM = .3
# Missing evidence and degenerate geometry arrive as these. A code defect
# (KeyError, TypeError) or a task time limit still stops the build.
_UNMEASURABLE = (ValueError, ArithmeticError)


def _failure_record(exc, stage):
    diagnostic = getattr(exc, 'diagnostic', None)
    return dict(diagnostic if isinstance(diagnostic, dict) else {'schema': 'line_width_evidence_error/1'},
                stage=stage, error_type=type(exc).__name__, error=str(exc))


def _measured_width(start, end, reference, size, junctions, stage):
    """Width and evidence, or None and the failure record; never raises for unmeasurable evidence."""
    try:
        width, record = _pictured_width(start, end, reference, size, junctions)
    except _UNMEASURABLE as exc:
        return None, None, _failure_record(exc, stage)
    return width, record, None


def _estimate_unmeasured_widths(widths, evidence, edges, nodes):
    """Width estimated: an unmeasurable segment takes this surface's median measured width."""
    measured = [width for width in widths if width is not None]
    if measured:
        estimate, source = float(np.median(measured)), 'median_of_measured_segments_on_this_surface'
    else:
        estimate, source = DEFAULT_FOIL_WIDTH_MM, 'default_foil_width'
    estimated = []
    for index, width in enumerate(widths):
        if width is not None:
            continue
        widths[index] = estimate
        evidence[index].update(stroke_width_mm=estimate, estimate_source=source,
                               measured_segment_count=len(measured))
        left, right = edges[index]
        estimated.append({'segment_index': index, 'status': 'width estimated',
            'endpoints_mm': [nodes[left].tolist(), nodes[right].tolist()],
            'stroke_width_mm': estimate, 'estimate_source': source, 'measured_segment_count': len(measured),
            'reason': evidence[index]['measurement_failure'].get('reason', evidence[index]['measurement_failure']['error'])})
    return estimated


def _inputs(image, line_mask, size_mm, width_mm):
    if isinstance(image, (str, Path)):
        rgb = np.asarray(Image.open(image).convert('RGB'))
    else:
        rgb = np.asarray(image)
    mask = np.asarray(line_mask)
    size = np.asarray(size_mm, dtype=float)
    if (rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3 or
            mask.dtype != bool or mask.shape != rgb.shape[:2] or not mask.any()):
        raise ValueError('An RGB uint8 picture and nonempty, same-size boolean motif mask are required')
    if (size.shape != (2,) or not np.isfinite(size).all() or np.any(size <= 0) or
            isinstance(width_mm, bool) or not math.isfinite(width_mm) or width_mm <= 0):
        raise ValueError('Physical panel size and stroke width must be positive finite millimetres')
    return rgb, mask, size


def _axis(points, direction):
    centre = points.mean(axis=0)
    _, _, basis = np.linalg.svd(points-centre, full_matrices=False)
    vector = basis[0]
    if vector @ direction < 0:
        vector = -vector
    projected = (points-centre) @ vector
    return centre+vector*projected.min(), centre+vector*projected.max()


def _near_axis(points, start, end, radius, extension):
    vector = end-start
    length = float(np.linalg.norm(vector))
    unit = vector/length
    offset = points-start
    along = offset @ unit
    across = np.abs(offset[:, 0]*unit[1]-offset[:, 1]*unit[0])
    return (across <= radius) & (along >= -extension) & (along <= length+extension)


def _consolidate_axes(axes, points, radius, extension):
    """Reach a fixed point: a merge may make an earlier pair duplicates."""
    axes = list(axes)
    while True:
        merged = False
        for first, (a, b) in enumerate(axes):
            unit = (b-a)/np.linalg.norm(b-a)
            for second in range(first+1, len(axes)):
                start, end = axes[second]
                direction = (end-start)/np.linalg.norm(end-start)
                if abs(unit @ direction) < math.cos(math.radians(4)):
                    continue
                midpoint = (start+end)/2
                distance = abs((midpoint-a)[0]*unit[1]-(midpoint-a)[1]*unit[0])
                projection = np.array([(start-a) @ unit, (end-a) @ unit])
                if (distance > radius or projection.max() < -extension or
                        projection.min() > np.linalg.norm(b-a)+extension):
                    continue
                lo = min(0., float(projection.min()))
                hi = max(float(np.linalg.norm(b-a)), float(projection.max()))
                selected = _near_axis(points, a+unit*lo, a+unit*hi, radius, 0.)
                if selected.sum() < 3:
                    continue
                axes[first] = _axis(points[selected], unit)
                axes.pop(second)
                merged = True
                break
            if merged:
                break
        if not merged:
            return axes


def _collapse_straight_nodes(nodes, edges):
    """Remove bookkeeping splits only; every true meeting remains a node."""
    edges = list(edges)
    while True:
        neighbours = {}
        for a, b in edges:
            neighbours.setdefault(a, []).append(b)
            neighbours.setdefault(b, []).append(a)
        changed = False
        for middle, ends in neighbours.items():
            if len(ends) != 2:
                continue
            a, b = ends
            u, v = nodes[a]-nodes[middle], nodes[b]-nodes[middle]
            if u @ v >= 0 or abs(u[0]*v[1]-u[1]*v[0]) > 1e-9:
                continue
            edges.remove(tuple(sorted((a, middle))))
            edges.remove(tuple(sorted((b, middle))))
            edges.append(tuple(sorted((a, b))))
            changed = True
            break
        if not changed:
            return edges


def _candidate_axes(mask, size, width):
    h, w = mask.shape
    scale = size/np.array([w, h])
    thin = skeleton(mask)
    ys, xs = np.where(thin)
    points = (np.column_stack((xs, ys))+.5)*scale
    minimum = max(5, round(min(h, w)*.035))
    gap = max(3, round(width/min(scale)*2))
    raw = cv2.HoughLinesP(thin.astype(np.uint8)*255, 1, np.pi/720,
                          threshold=max(7, minimum), minLineLength=minimum, maxLineGap=gap)
    if raw is None:
        return [], scale
    candidates = []
    radius = max(width*.6, float(max(scale))*1.25)
    extension = max(width*2, float(max(scale))*3)
    for row in raw.reshape(-1, 4):
        start = (row[:2]+.5)*scale; end = (row[2:]+.5)*scale
        if np.linalg.norm(end-start) < width*2:
            continue
        for _ in range(3):
            selected = _near_axis(points, start, end, radius, extension)
            if selected.sum() < 3:
                break
            start, end = _axis(points[selected], end-start)
        candidates.append((start, end))
    candidates.sort(key=lambda pair: -float(np.linalg.norm(pair[1]-pair[0])))
    axes = []
    for start, end in candidates:
        direction = (end-start)/np.linalg.norm(end-start)
        merged = False
        for index, (a, b) in enumerate(axes):
            unit = (b-a)/np.linalg.norm(b-a)
            if abs(unit @ direction) < math.cos(math.radians(4)):
                continue
            middle = (start+end)/2
            distance = abs((middle-a)[0]*unit[1]-(middle-a)[1]*unit[0])
            projections = np.array([(start-a) @ unit, (end-a) @ unit])
            if (distance > radius or projections.max() < -extension or
                    projections.min() > np.linalg.norm(b-a)+extension):
                continue
            lo = min(0., float(projections.min()))
            hi = max(float(np.linalg.norm(b-a)), float(projections.max()))
            selected = _near_axis(points, a+unit*lo, a+unit*hi, radius, 0.)
            axes[index] = _axis(points[selected], unit)
            merged = True
            break
        if not merged:
            axes.append((start, end))
    return _consolidate_axes(axes, points, radius, extension), scale


def _network(axes, snap):
    """Split true meetings and snap observed near-endpoints to shared nodes."""
    cuts = [[(0., a), (1., b)] for a, b in axes]
    for first, (a, b) in enumerate(axes):
        u = b-a
        for second in range(first+1, len(axes)):
            c, d = axes[second]; v = d-c
            determinant = u[0]*v[1]-u[1]*v[0]
            if abs(determinant) < 1e-9:
                continue
            t, s = np.linalg.solve(np.column_stack((u, -v)), c-a)
            if (-snap/np.linalg.norm(u) <= t <= 1+snap/np.linalg.norm(u) and
                    -snap/np.linalg.norm(v) <= s <= 1+snap/np.linalg.norm(v)):
                node = a+t*u
                cuts[first].append((float(t), node)); cuts[second].append((float(s), node))
    nodes = []
    segments = []
    for entries in cuts:
        ordered = []
        for _, point in sorted(entries, key=lambda row: row[0]):
            near = [index for index, existing in enumerate(nodes) if np.linalg.norm(point-existing) <= snap]
            if near:
                index = near[0]
            else:
                index = len(nodes); nodes.append(point)
            if not ordered or ordered[-1] != index:
                ordered.append(index)
        for left, right in zip(ordered, ordered[1:]):
            pair = tuple(sorted((left, right)))
            if pair not in segments and np.linalg.norm(nodes[left]-nodes[right]) >= snap:
                segments.append(pair)
    return nodes, segments


def _support(start, end, tree, width, pixel_mm):
    length = float(np.linalg.norm(end-start))
    count = max(3, int(math.ceil(length/min(pixel_mm)*2))+1)
    distances, _ = tree.query(np.linspace(start, end, count))
    supported = distances <= max(width*.6, float(max(pixel_mm))*1.5)
    longest = current = 0
    for value in supported:
        if value:
            current = 0
        else:
            current += 1; longest = max(longest, current)
    gap = longest*length/(count-1)
    fraction = float(supported.mean())
    return {'length_mm': length, 'centreline_source_support': fraction,
            'longest_unsupported_mm': gap, 'supported': fraction >= .8 and gap <= width*3}


def _pictured_width(start, end, mask, size, junctions):
    """Measure original pixel-cell cross sections, independently of coverage."""
    h, w = mask.shape
    scale = size/np.array([w, h])
    vector = end-start
    length = float(np.linalg.norm(vector))
    normal = np.array([-vector[1], vector[0]])/length
    step = 1/float(np.linalg.norm(normal/scale))/8
    extent = float(np.linalg.norm(size))
    offsets = np.arange(-extent, extent+step, step)
    samples = []
    for fraction in np.linspace(.1, .9, min(501, max(25, int(length/max(scale))))):
        centre = start+fraction*vector
        positions = centre+offsets[:, None]*normal
        pixels = np.floor(positions/scale).astype(int)
        valid = (pixels[:, 0] >= 0) & (pixels[:, 0] < w) & (pixels[:, 1] >= 0) & (pixels[:, 1] < h)
        present = np.zeros(len(offsets), bool)
        present[valid] = mask[pixels[valid, 1], pixels[valid, 0]]
        choices = np.flatnonzero(present & (np.abs(offsets) <= max(scale)*1.5))
        if not len(choices):
            continue
        middle = choices[np.argmin(np.abs(offsets[choices]))]
        left = right = int(middle)
        while left > 0 and present[left-1]:
            left -= 1
        while right+1 < len(present) and present[right+1]:
            right += 1
        bounds = [offsets[left]-step/2, offsets[right]+step/2]
        samples.append({'centre_original_px': (centre/scale-.5).tolist(),
            'original_station_cell': np.floor(centre/scale).astype(int).tolist(),
            'bounds_original_px': [((centre+bound*normal)/scale-.5).tolist() for bound in bounds],
            'width_mm': float(bounds[1]-bounds[0]),
            'nearest_junction_mm': min((float(np.linalg.norm(centre-node)) for node in junctions), default=None)})
    if len(samples) < 5:
        raise _width_failure('Too little original cross-section evidence for a pictured stroke width',
                             start, end, mask, samples, 'too_few_original_sections')
    preliminary = float(np.median([row['width_mm'] for row in samples]))
    for row in samples:
        row['accepted'] = bool((row['nearest_junction_mm'] is None or row['nearest_junction_mm'] > preliminary*1.5+max(scale))
                              and row['width_mm'] <= preliminary*1.5)
    accepted = [row['width_mm'] for row in samples if row['accepted']]
    stations = {tuple(row['original_station_cell']) for row in samples if row['accepted']}
    if len(accepted) < 5 or len(stations) < 3:
        raise _width_failure('Original stroke width is obscured by meeting nodes',
                             start, end, mask, samples, 'insufficient_independent_off_junction_sections')
    width = float(np.mean(accepted))
    return width, {'method': 'Mean original pixel-cell width across uniformly spaced perpendicular sections; meeting-neighbourhood and broad junction sections excluded before width choice. Averaging retains pixel-grid width variation. No coverage feedback.',
        'reference_size_px': [w, h], 'sampling_step_mm': step, 'samples': samples,
        'accepted_samples': len(accepted), 'independent_original_station_cells': len(stations),
        'minimum_independent_station_cells': 3, 'stroke_width_mm': width}


def _pictured_axes(axes, reference, size):
    """A broad meeting's skeleton bisector is not an additional printed line."""
    scale = size/np.array([reference.shape[1], reference.shape[0]])
    retained = []
    widths = []
    rejected = []
    for start, end in sorted(axes, key=lambda pair: -float(np.linalg.norm(pair[1]-pair[0]))):
        points = np.linspace(start, end, max(5, int(np.linalg.norm(end-start)/min(scale)*2)))
        explained = np.zeros(len(points), bool)
        for (a, b), width in zip(retained, widths):
            vector = b-a
            position = np.clip((points-a) @ vector/(vector @ vector), 0, 1)
            distance = np.linalg.norm(points-(a+position[:, None]*vector), axis=1)
            explained |= distance <= width/2+float(max(scale))*.75
        if explained.all():
            rejected.append({'endpoints_mm': [start.tolist(), end.tolist()],
                'reason': 'Entire candidate centreline lies within longer observed ridges at their independently measured widths, including one-pixel boundary uncertainty.'})
            continue
        width, _, failure = _measured_width(start, end, reference, size, [], 'candidate_selection')
        if failure is not None:
            rejected.append({'endpoints_mm': [start.tolist(), end.tolist()],
                'reason': 'Candidate has insufficient original width evidence; its source pixels remain in both coverage denominators.',
                'diagnostic': failure})
            continue
        retained.append((start, end)); widths.append(width)
    return retained, rejected


def _refine_pictured_axes(axes, reference, size):
    """Fit the observed ridge's middle, rather than a bevel-biased skeleton."""
    scale = size/np.array([reference.shape[1], reference.shape[0]])
    refined, records = [], []
    for start, end in axes:
        # An insignificant raw proposal is rejected here, before duplicate
        # rejection; it never aborts the panel. It is never drawn either.
        _, evidence, failure = _measured_width(start, end, reference, size, [], 'candidate_refinement')
        if failure is not None:
            records.append({'status': 'rejected', 'proposal_endpoints_mm': [start.tolist(), end.tolist()],
                'diagnostic': failure, 'source_pixels_removed_from_denominator': 0})
            continue
        centres = np.array([(np.mean(row['bounds_original_px'], axis=0)+.5)*scale
                            for row in evidence['samples'] if row['accepted']])
        a, b = _axis(centres, end-start)
        unit = (b-a)/np.linalg.norm(b-a)
        centre = centres.mean(axis=0)
        pair = (centre+((start-centre) @ unit)*unit, centre+((end-centre) @ unit)*unit)
        refined.append(pair)
        records.append({'status': 'refined', 'proposal_endpoints_mm': [start.tolist(), end.tolist()],
            'refined_endpoints_mm': [point.tolist() for point in pair],
            'accepted_original_sections': len(centres),
            'maximum_endpoint_shift_mm': float(max(np.linalg.norm(pair[0]-start), np.linalg.norm(pair[1]-end)))})
    return refined, records


def _pictured_network(axes, reference, size):
    """Resolve source-supported meetings before making edges; never erase bridges."""
    scale = size/np.array([reference.shape[1], reference.shape[0]])
    uncertainty = float(np.linalg.norm(scale))/2
    # Widths only size the meeting overlap here; the fitter's axes all
    # measured already, so the fallback guards direct callers only.
    widths = [_measured_width(a, b, reference, size, [], 'network')[0] for a, b in axes]
    known = [width for width in widths if width is not None]
    widths = [(float(np.median(known)) if known else DEFAULT_FOIL_WIDTH_MM) if width is None else width
              for width in widths]
    units =[(b-a)/np.linalg.norm(b-a) for a, b in axes]
    normals = [np.array([-unit[1], unit[0]]) for unit in units]
    yy, xx = np.where(reference)
    tree = cKDTree((np.column_stack((xx, yy))+.5)*scale)
    meetings = []
    for first, (a, b) in enumerate(axes):
        for second in range(first+1, len(axes)):
            c, d = axes[second]
            sine = abs(float(np.linalg.det(np.stack((units[first], units[second])))))
            if sine < math.sin(math.radians(4)):
                continue
            lengths = np.linalg.solve(np.column_stack((units[first], -units[second])), c-a)
            extent = (max(widths[first], widths[second])/2+uncertainty)/sine
            if not (-extent <= lengths[0] <= np.linalg.norm(b-a)+extent and
                    -extent <= lengths[1] <= np.linalg.norm(d-c)+extent):
                continue
            point = a+lengths[0]*units[first]
            if tree.query(point)[0] > uncertainty+min(scale)/2:
                continue
            meetings.append({'point': point, 'axes': {first, second},
                             'axis_extents': {first: extent, second: extent}})
    while True:
        changed = False
        for first, left in enumerate(meetings):
            for second in range(first+1, len(meetings)):
                right = meetings[second]
                if not left['axes'] & right['axes']:
                    continue
                members = sorted(left['axes'] | right['axes'])
                # Two nearby crossings with independent parallel branches are
                # distinct nodes, even when their ink touches at low resolution.
                if any(abs(units[a] @ units[b]) > math.cos(math.radians(4))
                       for i, a in enumerate(members) for b in members[i+1:]):
                    continue
                matrix = np.array([normals[index] for index in members])
                intercepts = np.array([normals[index] @ axes[index][0] for index in members])
                point = np.linalg.lstsq(matrix, intercepts, rcond=None)[0]
                if (np.max(np.abs(matrix @ point-intercepts)) > uncertainty or
                        tree.query(point)[0] > uncertainty+min(scale)/2):
                    continue
                meetings[first] = {'point': point, 'axes': set(members),
                    'axis_extents': {axis: max(row['axis_extents'][axis] for row in (left, right)
                                              if axis in row['axis_extents']) for axis in members}}
                meetings.pop(second); changed = True
                break
            if changed:
                break
        if not changed:
            break
    nodes = [row['point'] for row in meetings]
    edges = []
    edge_parents = {}
    for axis, (start, end) in enumerate(axes):
        entries = [(float((row['point']-start) @ units[axis]), index)
                   for index, row in enumerate(meetings) if axis in row['axes']]
        for point in (start, end):
            close = [(float(np.linalg.norm(point-row['point'])), index) for index, row in enumerate(meetings)
                     if axis in row['axes'] and np.linalg.norm(point-row['point']) <= row['axis_extents'][axis]]
            if close:
                index = min(close)[1]
            else:
                index = len(nodes); nodes.append(point)
            position = float((nodes[index]-start) @ units[axis])
            if (position, index) not in entries:
                entries.append((position, index))
        ordered = [index for _, index in sorted(entries)]
        for a, b in zip(ordered, ordered[1:]):
            edge = tuple(sorted((a, b)))
            if a != b and edge not in edges:
                edges.append(edge)
            if a != b:
                if edge not in edge_parents:
                    edge_parents[edge] = set()
                edge_parents[edge].add(axis)
    evidence = {'method': 'Original cross-section centre axes; source-supported intersections consolidated only within half a source-pixel diagonal of every incident axis. Endpoint bevels snap inside the observed joint strip overlap. No post-network bridge deletion.',
        'source_pixel_uncertainty_mm': uncertainty,
        'meetings': [{'point_mm': row['point'].tolist(), 'axis_indices': sorted(row['axes']),
                      'endpoint_overlap_by_axis_mm': {str(axis): extent for axis, extent in row['axis_extents'].items()}}
                     for row in meetings],
        'parent_axes': [{'axis_index': index, 'endpoints_mm': [a.tolist(), b.tolist()]}
                        for index, (a, b) in enumerate(axes)],
        'edge_parent_axes': [{'node_indices': list(edge), 'axis_indices': sorted(edge_parents[edge])}
                             for edge in edges]}
    return nodes, edges, evidence


def _continuous_parent_axes(edge, original_edges, network):
    """Follow the recorded axis through any exact collinear node collapse."""
    allowed = set(original_edges)
    matched = []
    for parent in network['parent_axes']:
        axis = parent['axis_index']
        neighbours = {}
        for row in network['edge_parent_axes']:
            a, b = row['node_indices']
            if (a, b) not in allowed or axis not in row['axis_indices']:
                continue
            if a not in neighbours:
                neighbours[a] = set()
            if b not in neighbours:
                neighbours[b] = set()
            neighbours[a].add(b); neighbours[b].add(a)
        seen = {edge[0]}; pending = [edge[0]]
        while pending:
            current = pending.pop()
            if current not in neighbours:
                continue
            for other in neighbours[current]-seen:
                seen.add(other); pending.append(other)
        if edge[1] in seen:
            matched.append(axis)
    return matched


def _segment_pictured_width(start, end, reference, size, junctions, parents, axes):
    """Use direct evidence, or agreeing original flanks of one continuous ridge."""
    try:
        width, record = _pictured_width(start, end, reference, size, junctions)
        record['evidence_scope'] = 'this_segment'
        return width, record
    except WidthEvidenceError as local_error:
        diagnostic = dict(local_error.diagnostic, stage='final_segment_width', parent_axis_indices=parents)
    if len(parents) != 1:
        diagnostic['reason'] = 'short_segment_has_no_unique_continuous_parent'
        raise WidthEvidenceError('A short segment needs one uniquely identified continuous parent ridge', diagnostic)
    parent = parents[0]
    a, b = axes[parent]
    unit = (b-a)/np.linalg.norm(b-a)
    scale = size/np.array([reference.shape[1], reference.shape[0]])
    try:
        _, parent_record = _pictured_width(a, b, reference, size, junctions)
        samples = parent_record['samples']
    except WidthEvidenceError as parent_error:
        samples = parent_error.diagnostic['samples']
    # Inspect every original section, not just the prior width-outlier filter:
    # a true thickness change must not disappear as a supposed broad junction.
    off_junction = [row for row in samples if row['nearest_junction_mm'] is None or
                    row['nearest_junction_mm'] > row['width_mm']*1.5+float(max(scale))]
    if not off_junction:
        diagnostic['reason'] = 'parent_has_no_off_junction_sections'
        raise WidthEvidenceError('The parent ridge has no independent off-junction width evidence', diagnostic)
    nominal = float(np.median([row['width_mm'] for row in off_junction]))
    reach = max(nominal*4, float(max(scale))*5)
    lo, hi = sorted([float((point-a) @ unit) for point in (start, end)])
    flanks = [[], []]
    for row in off_junction:
        position = float(((np.array(row['centre_original_px'])+.5)*scale-a) @ unit)
        if lo-reach <= position < lo:
            flanks[0].append(row)
        elif hi < position <= hi+reach:
            flanks[1].append(row)
    audit = []
    for side, rows in zip(('before', 'after'), flanks):
        cells = {tuple(row['original_station_cell']) for row in rows}
        audit.append({'side': side, 'samples': rows, 'sample_count': len(rows),
                      'independent_original_station_cells': len(cells)})
    diagnostic['parent_flanks'] = audit
    diagnostic['parent_endpoints_mm'] = [a.tolist(), b.tolist()]
    if any(row['sample_count'] < 5 or row['independent_original_station_cells'] < 3 for row in audit):
        diagnostic['reason'] = 'parent_flanks_lack_independent_original_evidence'
        raise WidthEvidenceError('Both sides of a short segment need independent original width evidence', diagnostic)
    widths = [float(np.mean([row['width_mm'] for row in rows])) for rows in flanks]
    uncertainty = float(np.linalg.norm(scale))
    if abs(widths[0]-widths[1]) > uncertainty:
        diagnostic.update(reason='parent_width_changes_across_segment', flank_widths_mm=widths,
                          source_width_agreement_tolerance_mm=uncertainty)
        raise WidthEvidenceError('The original parent ridge changes width across the short segment', diagnostic)
    width = float(np.mean(widths))
    return width, {'method': 'Agreeing original off-junction cross sections on both sides of this split, from its unique continuous parent axis only. No global or neighbouring ridge width and no coverage feedback.',
        'evidence_scope': 'continuous_parent_flanks', 'parent_axis_index': parent,
        'parent_endpoints_mm': [a.tolist(), b.tolist()], 'local_insufficiency': diagnostic,
        'reference_size_px': [reference.shape[1], reference.shape[0]], 'parent_flanks': audit,
        'flank_widths_mm': widths, 'source_width_agreement_tolerance_mm': uncertainty,
        'maximum_flank_distance_mm': reach, 'stroke_width_mm': width,
        'independent_original_station_cells': sum(row['independent_original_station_cells'] for row in audit)}


def measure_line_network(svg_path, line_mask, size_mm, width_mm=.3, *, width_mode='fixed'):
    """Read the emitted geometry, including any added paths, then measure it."""
    mask = np.asarray(line_mask)
    size = np.asarray(size_mm, dtype=float)
    if width_mode not in ('fixed', 'pictured'):
        raise ValueError('Unknown line-width mode')
    support_width = min(width_mm, .3) if width_mode == 'pictured' else width_mm
    h, w = mask.shape; scale = size/np.array([w, h])
    yy, xx = np.where(mask)
    tree = cKDTree((np.column_stack((xx, yy))+.5)*scale)
    data = Path(svg_path).read_bytes(); root = ET.fromstring(data)
    if [float(value) for value in root.attrib['viewBox'].split()] != [0., 0., *size.tolist()]:
        raise ValueError('The emitted SVG must use its physical millimetre viewBox')
    segments = []
    for path in root:
        if path.tag.rsplit('}', 1)[-1] != 'path':
            raise ValueError('A line network may contain only straight path elements')
        match = re.fullmatch(r'M\s*([\d.eE+-]+)[,\s]+([\d.eE+-]+)\s*L\s*([\d.eE+-]+)[,\s]+([\d.eE+-]+)\s*', path.attrib['d'])
        actual_width = float(path.attrib['stroke-width'])
        if (match is None or path.attrib['fill'] != 'none' or
                not math.isfinite(actual_width) or actual_width <= 0 or
                (width_mode == 'fixed' and abs(actual_width-width_mm) > 1e-9) or 'transform' in path.attrib):
            raise ValueError('Each motif segment must be one untransformed straight stroke with an allowed positive width')
        a, b, c, d = map(float, match.groups()); start = np.array([a, b]); end = np.array([c, d])
        row = _support(start, end, tree, support_width, scale)
        row.update(endpoints_mm=[start.tolist(), end.tolist()],
                   stroke_width_mm=actual_width,
                   endpoints_source_px=[(start/scale-.5).tolist(), (end/scale-.5).tolist()])
        segments.append(row)
    with fitz.open(stream=data, filetype='svg') as image:
        pdf = image.convert_to_pdf()
    with fitz.open(stream=pdf, filetype='pdf') as document:
        page = document[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(w*4/page.rect.width, h*4/page.rect.height), alpha=True)
        pixels = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
        alpha = cv2.resize(pixels[..., -1], (w, h), interpolation=cv2.INTER_AREA)
    covered = (alpha >= 128) & mask
    coverage = float(covered.sum()/mask.sum())
    all_supported = bool(segments) and all(row['supported'] for row in segments)
    return {'svg_sha256': hashlib.sha256(data).hexdigest(), 'segments': segments,
            'source_line_pixels': int(mask.sum()), 'covered_source_line_pixels': int(covered.sum()),
            'coverage': coverage, 'alpha_weighted_coverage': float(alpha[mask].mean()/255),
            'coverage_method': 'Actual emitted SVG rasterized at four times source resolution, area-reduced; source mask pixel is covered at alpha >= 128. Entire supplied mask is the denominator.',
            'minimum_coverage': .9, 'all_segments_supported': all_supported, 'width_mode': width_mode,
            'support_width_mm': support_width,
            'passed': coverage >= .9 and all_supported}


def fit_line_network(image, line_mask, size_mm, output_svg, width_mm=.3, *, width_mode='fixed', width_reference_mask=None):
    """Return measured straight-segment geometry; failed coverage stays explicit."""
    if isinstance(image, (str, Path)) and Path(image).resolve() == Path(output_svg).resolve():
        raise ValueError('The vector output must not replace the source picture')
    rgb, mask, size = _inputs(image, line_mask, size_mm, width_mm)
    if width_mode not in ('fixed', 'pictured'):
        raise ValueError('Unknown line-width mode')
    if width_mode == 'pictured':
        reference = np.asarray(width_reference_mask)
        if reference.dtype != bool or reference.ndim != 2 or not reference.any():
            raise ValueError('Pictured widths require the full original boolean motif mask')
    support_width = min(width_mm, .3) if width_mode == 'pictured' else width_mm
    before_image = hashlib.sha256(rgb.tobytes()).hexdigest()
    before_mask = hashlib.sha256(mask.tobytes()).hexdigest()
    axes, scale = _candidate_axes(mask, size, width_mm)
    explained_axes = []
    centre_records = []
    network_record = None
    if width_mode == 'pictured':
        axes, centre_records = _refine_pictured_axes(axes, reference, size)
        axes, explained_axes = _pictured_axes(axes, reference, size)
    snap = max(width_mm*.65, float(max(scale))*1.5)
    if width_mode == 'pictured':
        nodes, edges, network_record = _pictured_network(axes, reference, size)
    else:
        nodes, edges = _network(axes, snap)
    yy, xx = np.where(mask)
    tree = cKDTree((np.column_stack((xx, yy))+.5)*scale)
    supported_edges = []
    rejected = []
    for left, right in edges:
        support = _support(nodes[left], nodes[right], tree, support_width, scale)
        if support['supported']:
            supported_edges.append((left, right))
        else:
            rejected.append(dict(support, endpoints_mm=[nodes[left].tolist(), nodes[right].tolist()]))
    original_supported_edges = list(supported_edges)
    supported_edges = _collapse_straight_nodes(nodes, supported_edges)
    explained_edges = []
    degrees = [sum(index in edge for edge in supported_edges) for index in range(len(nodes))]
    junctions = [point for index, point in enumerate(nodes) if degrees[index] > 2]
    commands = []
    evidence = []
    widths = []
    for left, right in supported_edges:
        stroke_width, record = width_mm, None
        if width_mode == 'pictured':
            try:
                stroke_width, record = _segment_pictured_width(nodes[left], nodes[right], reference, size, junctions,
                    _continuous_parent_axes((left, right), original_supported_edges, network_record), axes)
                if not (math.isfinite(stroke_width) and stroke_width > 0):
                    raise ValueError('Measured stroke width is not a positive finite millimetre value')
            except _UNMEASURABLE as exc:
                # Filled once every segment of this surface has been measured.
                stroke_width, record = None, {'evidence_scope': 'width_estimated', 'width_estimated': True,
                    'method': 'Width estimated, not measured: no original cross-section evidence survived for this segment or its continuous parent ridge. It takes the median measured stroke width of this surface, or the 0.3 mm default foil width when none was measured; the build continues.',
                    'measurement_failure': _failure_record(exc, 'final_segment_width')}
        widths.append(stroke_width); evidence.append(record)
    estimated = _estimate_unmeasured_widths(widths, evidence, supported_edges, nodes)
    for (left, right), stroke_width in zip(supported_edges, widths):
        a, b = nodes[left]; c, d = nodes[right]
        commands.append(f'<path d="M {a:.8f},{b:.8f} L {c:.8f},{d:.8f}" fill="none" stroke="#D5AF59" stroke-width="{stroke_width:.8f}" stroke-linecap="round" stroke-linejoin="round"/>')
    target = Path(output_svg); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{size[0]:.8f}mm" height="{size[1]:.8f}mm" viewBox="0 0 {size[0]} {size[1]}">'+''.join(commands)+'</svg>')
    measured = measure_line_network(target, mask, size, width_mm, width_mode=width_mode)
    for row, record in zip(measured['segments'], evidence):
        row['width_evidence'] = record
    measured.update(schema='straight_line_network/1', svg=str(target.resolve()), size_mm=size.tolist(), width_mm=width_mm if width_mode == 'fixed' else None,
                    source_rgb_sha256=before_image, source_mask_sha256=before_mask,
                    source_pixels_unchanged=hashlib.sha256(rgb.tobytes()).hexdigest() == before_image,
                    source_mask_unchanged=hashlib.sha256(mask.tobytes()).hexdigest() == before_mask,
                    nodes_mm=[point.tolist() for point in nodes], segment_node_indices=[list(edge) for edge in supported_edges],
                    fitted_axis_count=len(axes),
                    rejected_explained_axes=explained_axes,
                    rejected_explained_segments=explained_edges,
                    pictured_axis_refinement=centre_records, pictured_meetings=network_record,
                    rejected_unsupported_segments=rejected,
                    width_estimated_segments=estimated,
                    method='Hough proposals on observed motif skeleton, physical-space least-squares lines, fixed-point duplicate-axis consolidation, shared meeting nodes and one straight stroke per supported segment. Only exactly collinear degree-two bookkeeping nodes collapse; source pixels and coverage mask stay unchanged.')
    if width_mode == 'pictured':
        measured['width_reference_mask_sha256'] = hashlib.sha256(reference.tobytes()).hexdigest()
        measured['width_reference_size_px'] = [reference.shape[1], reference.shape[0]]
    return measured
