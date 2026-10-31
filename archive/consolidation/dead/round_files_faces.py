"""Dead ends of apps/pipeline/services/round_files_faces.py, moved here verbatim (the owner's goal of 2026-10-29, §1: any function nothing calls is
listed and removed; nothing deleted). Nothing live or in the tests called them at the move: _face_for, drawing_findings, type_rows_of, upright_picture, write, zone_mask."""


def drawing_findings(findings):
    """The findings a redraw can act on: those about the art, not the live type."""
    return [row for row in findings if not TYPE_FINDING.search(row)]


def upright_picture(path, face):
    """A face's picture at the composer's 300 PPI, its bleed included."""
    W, H = face['w_mm'] + 2 * face['bleed_mm'], face['h_mm'] + 2 * face['bleed_mm']
    size = (int(round(W * K)), int(round(H * K)))
    with Image.open(path) as image:
        return np.asarray(image.convert('RGB').resize(size, Image.LANCZOS))


def type_rows_of(key, spec_list):
    if stand_face(key):
        stand = next(item for item in spec_list if item['id'] == 'stand')
        return [row for row in stand['type_runs'] if row['name'].split(':', 1)[0] == key]
    return next(item for item in spec_list if item['id'] == FACES[key]['object'])['type_runs']


def zone_mask(size, zone, crop):
    """Crop-local pixels of the pictured lettering band."""
    mask = np.zeros((size[1], size[0]), np.uint8)
    points = np.array([[x - crop[0], y - crop[1]] for x, y in zone['path_px']], np.int32)
    cv2.polylines(mask, [points], False, 255, thickness=max(1, math.ceil(zone['height_px'] * BAND_COVER)),
                  lineType=cv2.LINE_8)
    return mask > 0


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def _face_for(copy):
    return face_for(copy)


