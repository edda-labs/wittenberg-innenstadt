"""Wittenberg Innenstadt 3D – Geometrie-Builder (OSM -> Mesh)"""
import json, math, os
import numpy as np
import mapbox_earcut as earcut
from shapely.geometry import Polygon, MultiPolygon, LineString, box
from shapely.ops import unary_union
from shapely.geometry.polygon import orient

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
LAT0, LON0 = 51.86640, 12.64720
KY = 110574.0
KX = 111320.0 * math.cos(math.radians(LAT0))

# Modellgebiet (Meter, lokal)
X0, X1 = -780.0, 780.0
Y0, Y1 = -460.0, 620.0

def to_xy(c):
    return [((p[1] - LON0) * KX, (p[0] - LAT0) * KY) for p in c]

# ---------------------------------------------------------------- Farben
def hsv_shift(c, dh=0.0, s=1.0, v=1.0):
    c = np.array(c, dtype=float)
    return tuple(np.clip(c * v, 0, 1))

PLASTER = [(0.93,0.90,0.83),(0.90,0.86,0.76),(0.86,0.79,0.67),(0.83,0.76,0.63),
           (0.95,0.93,0.88),(0.88,0.82,0.71),(0.80,0.73,0.62),(0.91,0.87,0.79),
           (0.87,0.83,0.74),(0.94,0.91,0.86),(0.84,0.78,0.68),(0.89,0.85,0.77),
           (0.92,0.88,0.80),(0.79,0.74,0.66),(0.96,0.94,0.89),(0.85,0.80,0.70)]
ROOF = [(0.62,0.32,0.24),(0.55,0.27,0.20),(0.68,0.38,0.28),(0.48,0.24,0.19),
        (0.58,0.33,0.26),(0.42,0.24,0.22),(0.66,0.36,0.25)]
SLATE = (0.31,0.32,0.36)
STONE = (0.83,0.79,0.69)

# ---------------------------------------------------------------- Mesh-Helfer
class Mesh:
    def __init__(self):
        self.v = []   # positions
        self.uv = []  # uvs
        self.c = []   # colors
        self.f = []   # faces

    def add(self, verts, faces, color, uvs=None):
        off = len(self.v)
        self.v.extend(verts)
        if uvs is None:
            self.uv.extend([(0.0, 0.0)] * len(verts))
        else:
            self.uv.extend(uvs)
        self.c.extend([color] * len(verts))
        self.f.extend([[i + off for i in f] for f in faces])

    def tri_count(self):
        return len(self.f)

    def merge(self, other):
        self.add(other.v, other.f, (0,0,0), other.uv)
        # restore per-vertex colors
        n = len(other.v)
        self.c[-n:] = other.c

def poly_rings(poly):
    """gibt (exterior, [holes]) als np-Arrays in CCW/CW-Orientierung zurück"""
    poly = orient(poly, 1.0)
    ext = np.array(poly.exterior.coords)[:-1]
    holes = [np.array(r.coords)[::-1][:-1] for r in poly.interiors]  # CW
    return ext, holes

def triangulate(ext, holes):
    rings = [ext] + holes
    flat = np.ascontiguousarray(np.concatenate(rings).astype(np.float64))
    ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
    idx = earcut.triangulate_float64(flat, ends)
    return idx.reshape(-1, 3)

def add_prism(mesh, poly, z0, z1, color, wall_uv=6.0, flat_top=True, cap_color=None, bottom=True, top=True):
    """extrudiert ein Shapely-Polygon; liefert Mesh-Teile für Wände und Deckel"""
    ext, holes = poly_rings(poly)
    verts = np.concatenate([ext] + holes)
    tris = triangulate(ext, holes)
    base = len(mesh.v)
    # Wände (pro Ring)
    start = 0
    for ring in [ext] + holes:
        n = len(ring)
        for i in range(n):
            a = ring[i]; b = ring[(i + 1) % n]
            L = math.hypot(b[0]-a[0], b[1]-a[1])
            if L < 1e-6:
                continue
            vs = [(a[0],z0,a[1]),(b[0],z0,b[1]),(b[0],z1,b[1]),(a[0],z1,a[1])]
            u0, u1 = 0.0, L / wall_uv
            v0, v1 = z0 / wall_uv, z1 / wall_uv
            mesh.add(vs, [[0,1,2],[0,2,3]], color,
                      uvs=[(u0,v0),(u1,v0),(u1,v1),(u0,v1)])
        start += n
    # Deckel oben
    top_c = cap_color or color
    if top:
        vtop = [(p[0], z1, p[1]) for p in verts]
        mesh.add(vtop, tris.tolist(), top_c)
    if bottom:
        vbot = [(p[0], z0, p[1]) for p in verts]
        mesh.add(vbot, [[t[2], t[1], t[0]] for t in tris.tolist()], top_c)
    return mesh

def add_flat_poly(mesh, poly, z, color, uv_scale=8.0):
    ext, holes = poly_rings(poly)
    verts = np.concatenate([ext] + holes)
    tris = triangulate(ext, holes)
    vs = [(p[0], z, p[1]) for p in verts]
    uvs = [(p[0]/uv_scale, p[1]/uv_scale) for p in verts]
    mesh.add(vs, tris.tolist(), color, uvs=uvs)

# ---------------------------------------------------------------- Dach
def hip_roof(poly, z_eave, rise, rings=4, K=32):
    """Hüftdach durch Offset-Lofting (Buffer + Winkel-Resampling)."""
    C = poly.representative_point()
    cx, cy = C.x, C.y
    minx, miny, maxx, maxy = poly.bounds
    dmax = min((maxx-minx), (maxy-miny)) / 2.0 * 0.92
    if dmax < 0.8:
        return None
    dmax = min(dmax, 6.0)
    ang = np.linspace(0, 2*np.pi, K, endpoint=False)
    dirs = np.stack([np.cos(ang), np.sin(ang)], 1)
    ringlist = []
    for i in range(rings+1):
        d = dmax * i / rings
        g = poly.buffer(-d, join_style=2) if d > 0 else poly
        if g.is_empty:
            break
        if g.geom_type == 'MultiPolygon':
            g = max(g.geoms, key=lambda p: p.area)
        if g.area < 2.0:
            break
        ringlist.append((g, d))
    if len(ringlist) < 2:
        return None
    out_v, out_f, out_uv = [], [], []
    first_ring = None
    prev_pts = None
    for g, d in ringlist:
        pts = ray_ring(g, cx, cy, dirs)
        if first_ring is None:
            first_ring = pts
        z = z_eave + d * (rise / dmax)
        if prev_pts is not None:
            base = len(out_v)
            prev_z = prev_pts[1]
            for k in range(K):
                a = prev_pts[0][k]; b = prev_pts[0][(k+1)%K]
                c = pts[(k+1)%K];   e = pts[k]
                vs = [(a[0],prev_z,a[1]),(b[0],prev_z,b[1]),(c[0],z,c[1]),(e[0],z,e[1])]
                out_v.extend(vs)
                out_uv.extend([(0,0),(1,0),(1,1),(0,1)])
                out_f.append([base+i for i in (0,1,2)])
                out_f.append([base+i for i in (0,2,3)])
                base += 4
        prev_pts = (pts, z)
    if first_ring is not None:
        try:
            base_poly = Polygon([tuple(p) for p in first_ring])
            if base_poly.is_valid and base_poly.area > 0.5:
                ext, holes = poly_rings(base_poly)
                tris_b = triangulate(ext, holes)
                verts_b = np.concatenate([ext] + holes)
                base0 = len(out_v)
                for p in verts_b:
                    out_v.append((p[0], z_eave, p[1])); out_uv.append((0, 0))
                for t in tris_b.tolist():
                    out_f.append([base0 + t[0], base0 + t[2], base0 + t[1]])
        except Exception:
            pass

    # Ausreißer-Guard: zu lange Kanten => kein Loft-Dach
    if out_v:
        va = np.array(out_v)
        for f in out_f:
            pts3 = va[f]
            for i in range(3):
                if np.linalg.norm(pts3[i] - pts3[(i+1) % 3]) > 34.0:
                    return None
    # Deckel (Firstfläche) am Ende: echtes Triangulieren statt Fächer
    if prev_pts is not None:
        pts3, z = prev_pts
        try:
            cap = Polygon([(p[0], p[1]) for p in pts3])
            if not cap.is_valid: cap = cap.buffer(0)
        except Exception:
            cap = None
        if cap is not None and cap.geom_type == 'Polygon' and cap.area > 0.6:
            ext, holes = poly_rings(cap)
            tris = triangulate(ext, holes)
            verts = np.concatenate([ext] + holes)
            base = len(out_v)
            for p in verts:
                out_v.append((p[0], z, p[1])); out_uv.append((0, 0))
            for t in tris.tolist():
                out_f.append([base + t[0], base + t[1], base + t[2]])
    return out_v, out_f, out_uv

def ray_ring(g, cx, cy, dirs):
    """Schnittpunkte Strahlen vom Zentrum mit der Ringgrenze (Vektorform)"""
    ext = np.array(g.exterior.coords)[:-1]
    n = len(ext)
    a = ext; b = np.roll(ext, -1, axis=0)
    e = b - a
    out = np.zeros_like(dirs)
    for k, (dx, dy) in enumerate(dirs):
        # a + t*e = C + s*d
        den = e[:,1]*dx - e[:,0]*dy
        with np.errstate(divide='ignore', invalid='ignore'):
            s = ((a[:,0]-cx)*e[:,1] - (a[:,1]-cy)*e[:,0]) / (-den)
            t = ((a[:,0]-cx)*dy - (a[:,1]-cy)*dx) / den
        ok = (np.abs(den) > 1e-9) & (t >= 0) & (t <= 1) & (s > 0)
        if ok.any():
            ssel = s[ok]
            j = np.argmin(np.abs(ssel))
            out[k] = (cx + ssel[j]*dx, cy + ssel[j]*dy)
        else:
            # nächster Punkt auf dem Ring
            d2 = (ext[:,0]-cx)**2 + (ext[:,1]-cy)**2
            out[k] = ext[np.argmin(d2)]
    return out

def gable_roof(rect_coords, z_eave, rise, along='long'):
    """Satteldach über dem OBB-Rechteck"""
    p = np.array(rect_coords)
    # Kantenlängen
    L = [np.linalg.norm(p[i+1]-p[i]) for i in range(4)]
    if along == 'long':
        i0 = 0 if L[0] >= L[1] else 1
    else:
        i0 = 0 if L[0] < L[1] else 1
    # Kante i0 und i0+2 sind die Traufen? -> First verläuft parallel zu Kante i0
    a, b = p[i0], p[i0+1]
    c, d = p[i0+2], p[i0+3]
    mid = (a+b)/2
    # Firstlinie: von Mitte der einen Seite zur anderen
    # Verschiebe a,b zur Mitte der gegenüberliegenden Seite
    m1 = a; m2 = b
    # Richtung quer
    q1 = (a + d)/2; q2 = (b + c)/2
    r1 = (m1 + q1)/2; r2 = (m2 + q2)/2
    zr = z_eave + rise
    vs = [(a[0],z_eave,a[1]),(b[0],z_eave,b[1]),(c[0],z_eave,c[1]),(d[0],z_eave,d[1]),
          (r1[0],zr,r1[1]),(r2[0],zr,r2[1])]
    fs = [[0,1,5],[0,5,4],   # Längsseite 1
          [2,3,4],[3,5,4],   # Seite 2 (Orientierung später prüfen)
          [0,4,3],[0,3,2],   # Giebeldreieck
          [1,2,3],[1,3,5]]   # no-op, wird ersetzt
    fs = [[0,1,5],[0,5,4],[3,2,4],[2,5,4],[0,4,3],[1,2,5]]
    return vs, fs

def tower(cx, cy, w, h_wall, h_spire, kind='square', color=STONE, roof_color=(0.35,0.45,0.42),
          n=8, base_z=0.0):
    """Turm mit Wand + Spitzdach"""
    vs, fs = [], []
    if kind == 'square':
        pts = [(cx-w/2,cy-w/2),(cx+w/2,cy-w/2),(cx+w/2,cy+w/2),(cx-w/2,cy+w/2)]
    else:
        pts = [(cx + w/2*math.cos(2*math.pi*i/n), cy + w/2*math.sin(2*math.pi*i/n)) for i in range(n)]
    m = len(pts)
    for i in range(m):
        a = pts[i]; b = pts[(i+1) % m]
        base = len(vs)
        vs += [(a[0],base_z,a[1]),(b[0],base_z,b[1]),(b[0],h_wall,b[1]),(a[0],h_wall,a[1])]
        fs += [[base,base+1,base+2],[base,base+2,base+3]]
    # Spitze
    apex = len(vs); vs.append((cx, h_wall+h_spire, cy))
    ring0 = len(vs)
    for p in pts:
        vs.append((p[0],h_wall,p[1]))
    for i in range(m):
        fs.append([ring0+i, ring0+(i+1)%m, apex])
    return vs, fs, color, roof_color

# ---------------------------------------------------------------- Gebäude
TYPE_H = {
    'church': (16, 0.55), 'chapel': (10, 0.5), 'cathedral': (22, 0.5),
    'castle': (16, 0.45), 'fort': (12, 0.4),
    'residential': (10.5, 0.42), 'apartments': (11.5, 0.35), 'house': (9.0, 0.45),
    'detached': (8.5, 0.45), 'terrace': (8.5, 0.42), 'dormitory': (12, 0.35),
    'retail': (12, 0.3), 'commercial': (12, 0.3), 'office': (13, 0.28),
    'hotel': (13, 0.3), 'school': (12, 0.3), 'university': (14, 0.3),
    'college': (14, 0.3), 'hospital': (14, 0.3), 'public': (13, 0.3),
    'civic': (13, 0.3), 'government': (13, 0.3),
    'industrial': (9, 0.15), 'warehouse': (8, 0.15), 'factory': (9, 0.15),
    'garage': (3, 0.1), 'garages': (3, 0.1), 'shed': (2.8, 0.2), 'hut': (2.6, 0.25),
    'carport': (2.8, 0.1), 'roof': (3, 0.0), 'greenhouse': (3, 0.3),
    'yes': (10, 0.4), 'service': (6, 0.3), 'construction': (8, 0.3),
}
FLAT_TYPES = {'industrial','warehouse','factory','garage','garages','carport','roof','greenhouse'}

def height_of(t, area):
    if 'height' in t:
        try:
            h = float(str(t['height']).replace('m','').strip())
            if 2 < h < 200: return h
        except Exception: pass
    if 'building:levels' in t:
        try:
            lv = float(t['building:levels'])
            if 0 < lv < 30: return max(3.0, lv*3.1 + 1.0)
        except Exception: pass
    b = t.get('building', 'yes')
    h, roof = TYPE_H.get(b, (10, 0.4))
    return h + max(2.0, min(6.0, math.sqrt(max(area,20))*roof*0.9))
