"""Build-Skript: erzeugt Geometrie, STL und Web-Payload für Wittenberg Innenstadt 3D"""
import json, math, os, base64, gzip, sys
import numpy as np
import trimesh
from shapely.geometry import Polygon, MultiPolygon, LineString, box
from shapely.ops import unary_union
from shapely.geometry.polygon import orient

from build_model import (to_xy, Mesh, add_prism, add_flat_poly, hip_roof, tower,
                         height_of, poly_rings, triangulate,
                         PLASTER, ROOF, SLATE, STONE, FLAT_TYPES,
                         X0, X1, Y0, Y1, DATA)

rng = np.random.default_rng(7)

# ------------------------------------------------ Landmarken
LM = {
 'Schlosskirche': dict(kind='church', eave=17, rise=11, tower=dict(pos='west', w=9.0, h=44, sp=44, kind='oct')),
 'Schloss Wittenberg': dict(kind='castle', eave=16, rise=13),
 'Stadtkirche St. Marien': dict(kind='church', eave=19, rise=10, twins=dict(w=8.0, h=44, sp=16)),
 'Altes Rathaus': dict(kind='civic', eave=14, rise=10, turret=dict(w=4.2, h=30, sp=8)),
 'Neues Rathaus': dict(kind='civic', eave=14, rise=9),
 'Lutherhaus': dict(kind='house', eave=12, rise=11),
 'Melanchthonhaus': dict(kind='house', eave=12, rise=8),
 'Leucorea': dict(kind='university', eave=14, rise=9),
 'Augusteum': dict(kind='university', eave=15, rise=8),
 'Bugenhagenhaus': dict(kind='house', eave=10, rise=8),
 'Cranachhof': dict(kind='house', eave=11, rise=7),
 'Stadthaus': dict(kind='civic', eave=14, rise=9),
 'Melanchthon-Gymnasium': dict(kind='school', eave=14, rise=8),
 'Christine-Bourbeck-Haus': dict(kind='college', eave=12, rise=7),
}

LANDMARK_INFO = [
 ('Schlosskirche', 'Schlosskirche (Allerheiligenkirche)', 88.0,
  'Evangelische Schlosskirche, 1496–1503 als Nordflügel des Schlosses erbaut. Hier verbreitete Luther 1517 seine 95 Thesen; an der Thesentür. Turm 88 m hoch (Neubau 1885/92), Grablege von Luther und Melanchthon. UNESCO-Welterbe seit 1996.'),
 ('Schloss Wittenberg', 'Schloss Wittenberg', 32.0,
  'Residenzschloss der ernestinischen Kurfürsten, ab 1490 unter Friedrich dem Weisen neu erbaut. Dreiflügelanlage mit Schlosskirche als Nordflügel und zwei markanten Rundtürmen.'),
 ('Stadtkirche St. Marien', 'Stadtkirche St. Marien', 60.0,
  'Mutterkirche der Reformation: Predigtkirche Luthers und Bugenhagens, 1525 erste Deutsche Messe. 1187 erstmals erwähnt, dreischiffige Hallenkirche (1412–1439), zwei Türme mit barocken Hauben (um 1556), Höhe 60 m. Reformationsaltar von Cranach (1547).'),
 ('Altes Rathaus', 'Altes Rathaus', 30.0,
  'Renaissance-Rathaus, 1523–1541 errichtet, Fassade mit spätgotischen Vorhangbogenfenstern. Der Glockenturm mit der „Sünderglocke" kam 1573 hinzu.'),
 ('Lutherhaus', 'Lutherhaus', 22.0,
  'Ehemaliges Augustinereremitenkloster, ab 1504 Wohn- und Arbeitshaus Martin Luthers. Heute Reformationsgeschichtliches Museum, Teil des UNESCO-Welterbes.'),
 ('Melanchthonhaus', 'Melanchthonhaus', 20.0,
  '1536 für Philipp Melanchthon erbautes dreigeschossiges Gelehrtenhaus mit großem Garten; Wohn- und Sterbehaus des Reformators, heute Museum.'),
 ('Leucorea', 'Leucorea / Alte Universität', 26.0,
  '1502 gegründete Universität Wittenberg (Leucorea), Wirkungsstätte von Luther und Melanchthon. Das heutige Gebäude beherbergt die Stiftung Leucorea der Martin-Luther-Universität.'),
 ('Augusteum', 'Augusteum', 24.0,
  'Universitätsgebäude an der Collegienstraße, benannt nach Kurfürst August; klassizistischer Bau des 18. Jahrhunderts, Teil des Universitätsensembles.'),
 ('Bugenhagenhaus', 'Bugenhagenhaus', 18.0,
  'Wohnhaus von Johannes Bugenhagen, Luthers Beichtvater und Stadtpfarrer, der die Reformation in Norddeutschland und Skandinavien organisierte.'),
 ('Cranachhof', 'Cranachhof', 18.0,
  'Hof und Wohnhaus der Malerfamilie Cranach – Lucas Cranach der Ältere betrieb hier seine berühmte Werkstatt.'),
 ('Lutherdenkmal', 'Lutherdenkmal', 7.0,
  'Bronzestandbild Martin Luthers von Gottfried Schadow, gegossen 1821, auf dem Marktplatz vor dem Rathaus; eines der ersten öffentlichen Lutherdenkmäler.'),
 ('Melanchthondenkmal', 'Melanchthondenkmal', 8.0,
  'Neugotische Ädikula mit Standbild Philipp Melanchthons, 1865 eingeweiht, ebenfalls auf dem Marktplatz.'),
 ('Marktbrunnen', 'Marktbrunnen', 6.0,
  'Brunnen auf dem Marktplatz vor dem Alten Rathaus.'),
 ('Cranachdenkmal', 'Cranachdenkmal', 5.0,
  'Denkmal für Lucas Cranach den Älteren, der von 1505 bis 1553 in Wittenberg wirkte.'),
 ('Johannes Bugenhagen Statue', 'Bugenhagen-Statue', 5.0,
  'Denkmal für Johannes Bugenhagen nahe der Stadtkirche.'),
 ('Katharina von Bora', 'Katharina-von-Bora-Statue', 4.0,
  'Denkmal für Katharina von Bora, Luthers Ehefrau, die in Wittenberg das „Doktorhaus" führte.'),
]

def obb_pts(poly):
    r = poly.minimum_rotated_rectangle
    c = np.array(r.exterior.coords)[:-1]
    L = [float(np.linalg.norm(c[(i + 1) % 4] - c[i])) for i in range(4)]
    return c, L

EAVE = {'church':16.5,'chapel':10,'cathedral':22,'castle':16,'fort':12,
        'residential':11.0,'apartments':12.0,'house':9.5,'detached':8.5,'terrace':8.5,
        'dormitory':12.5,'retail':12.0,'commercial':12.5,'office':13.0,'hotel':13.5,
        'school':13.0,'university':14.0,'college':14.0,'hospital':14.0,'public':13.0,
        'civic':13.5,'government':13.5,'industrial':9.0,'warehouse':8.0,'factory':9.0,
        'garage':2.8,'garages':2.8,'shed':2.8,'hut':2.6,'carport':2.8,'roof':3.0,
        'greenhouse':3.0,'service':6.0,'yes':10.5,'construction':8.0}
def eave_of(t):
    return EAVE.get(t.get('building','yes'), 10.5)

def rot(cx, cy, pts, ang, sx=1.0, sy=1.0):
    ca, sa = math.cos(ang), math.sin(ang)
    out = []
    for (x, y) in pts:
        x, y = x*sx, y*sy
        out.append((cx + x*ca - y*sa, cy + x*sa + y*ca))
    return out

def rect_pts(cx, cy, w, h, ang=0.0):
    return rot(cx, cy, [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)], ang)

def add_tower(mesh, cx, cy, w, h_wall, h_spire, color, roof_color, kind='square', base_z=0.0):
    if kind == 'square':
        pts = rect_pts(cx, cy, w, w); n = 4
    else:
        n = 8
        pts = [(cx + w/2*math.cos(2*math.pi*i/n + math.pi/8), cy + w/2*math.sin(2*math.pi*i/n + math.pi/8)) for i in range(n)]
    base = len(mesh.v)
    for i in range(n):
        a = pts[i]; b = pts[(i+1) % n]
        L = math.hypot(b[0]-a[0], b[1]-a[1])
        vs = [(a[0],base_z,a[1]),(b[0],base_z,b[1]),(b[0],h_wall,b[1]),(a[0],h_wall,a[1])]
        mesh.add(vs, [[0,1,2],[0,2,3]], color, uvs=[(0,base_z/6),(L/6,base_z/6),(L/6,h_wall/6),(0,h_wall/6)])
    # Sohle
    base0 = len(mesh.v)
    for p in pts:
        mesh.v.append((p[0], base_z, p[1])); mesh.uv.append((0,0)); mesh.c.append(color)
    for i in range(1, n-1):
        mesh.f.append([base0, base0+i, base0+i+1])
    # Spitze / Haube
    base = len(mesh.v)
    ring = [(p[0], h_wall, p[1]) for p in pts]
    for p in ring: mesh.v.append(p); mesh.uv.append((0,0)); mesh.c.append(roof_color)
    apex = len(mesh.v); mesh.v.append((cx, h_wall+h_spire, cy)); mesh.uv.append((0,0)); mesh.c.append(roof_color)
    for i in range(n):
        mesh.f.append([base+i, base+(i+1)%n, apex])
    # kleiner Abschluss (Kugel/Knauf)
    return mesh

def add_box(mesh, cx, cy, w, d, z0, z1, ang, color):
    pts = rect_pts(cx, cy, w, d, ang)
    ext = np.array(pts)
    tris = triangulate(ext, [])
    verts = [(p[0], p[1]) for p in pts]
    for i in range(4):
        a = verts[i]; b = verts[(i+1) % 4]
        mesh.add([(a[0],z0,a[1]),(b[0],z0,b[1]),(b[0],z1,b[1]),(a[0],z1,a[1])],
                 [[0,1,2],[0,2,3]], color)
    vs = [(p[0], z1, p[1]) for p in verts]
    mesh.add(vs, tris.tolist(), color)
    vb = [(p[0], z0, p[1]) for p in verts]
    mesh.add(vb, [[t[2], t[1], t[0]] for t in tris.tolist()], color)

# ------------------------------------------------ Laden
F = json.load(open(os.path.join(DATA, 'features.json')))
POIS = json.load(open(os.path.join(DATA, 'pois.json')))

def clip_box():
    return box(X0, Y0, X1, Y1)

buildings, roads, waters, greens, walls_, pitches = [], [], [], [], [], []
for f in F:
    t = f['t']
    if 'building' in t and t.get('building') not in ('roof', 'no', None):
        rings = [to_xy(f['c'])] + [to_xy(r) for r in (f.get('inner') or [])]
        try:
            poly = Polygon(rings[0], rings[1:])
        except Exception:
            continue
        if not poly.is_valid: poly = poly.buffer(0)
        if poly.is_empty or poly.geom_type != 'Polygon' or poly.area < 6: continue
        b = poly.representative_point()
        if not (X0 <= b.x <= X1 and Y0 <= b.y <= Y1): continue
        buildings.append((f, poly))
    elif 'highway' in t:
        pts = to_xy(f['c'])
        if len(pts) < 2: continue
        if max(p[0] for p in pts) < X0 or min(p[0] for p in pts) > X1: continue
        if max(p[1] for p in pts) < Y0 or min(p[1] for p in pts) > Y1: continue
        roads.append((t, pts))
    elif t.get('natural') == 'water':
        p = Polygon(to_xy(f['c']))
        if p.is_valid and p.area > 30: waters.append(p)
    elif t.get('leisure') in ('park', 'garden', 'common', 'playground', 'pitch'):
        p = Polygon(to_xy(f['c']))
        if p.is_valid and p.area > 60: greens.append(p)
    elif 'landuse' in t and t['landuse'] in ('grass','forest','cemetery','village_green','recreation_ground'):
        p = Polygon(to_xy(f['c']))
        if p.is_valid and p.area > 200: greens.append(p)
    elif 'barrier' in t and t['barrier'] in ('city_wall', 'wall'):
        walls_.append(to_xy(f['c']))

print('Gebäude im Modell:', len(buildings), 'Straßen:', len(roads))

# ------------------------------------------------ Meshes
M_wall = Mesh(); M_roof = Mesh(); M_ground = Mesh(); M_props = Mesh()
landmark_pts = []

used_landmarks = set()
for f, poly in buildings:
    name = f['n']; t = f['t']
    spec = LM.get(name) if name in LM else None
    area = poly.area
    # Farbe
    if spec:
        base_col = STONE if spec['kind'] in ('church','castle','civic','university','college') else (0.88,0.82,0.70)
        roof_col = SLATE if spec['kind'] in ('church','castle') else (0.55,0.30,0.24)
    else:
        base_col = PLASTER[rng.integers(len(PLASTER))]
        roof_col = ROOF[rng.integers(len(ROOF))]
    btype = t.get('building', 'yes')

    if spec:
        eave = spec['eave']; roof_h = spec['rise']
        h = eave + roof_h
    else:
        roof_h = max(2.8, min(6.5, 0.30 * min(math.sqrt(max(area, 20)), 20)))
        if 'height' in t:
            try: eave = max(3.0, float(str(t['height']).replace('m','').strip()) - roof_h)
            except Exception: eave = eave_of(t) * float(rng.uniform(0.9, 1.1))
        elif 'building:levels' in t:
            try: eave = max(3.0, float(t['building:levels']) * 3.15 + 0.8)
            except Exception: eave = eave_of(t) * float(rng.uniform(0.9, 1.1))
        else:
            eave = eave_of(t) * float(rng.uniform(0.88, 1.12))
        h = eave + roof_h
    # Dachform zuerst bestimmen (Deckel des Baukörpers ggf. einsparen)
    flat = (btype in FLAT_TYPES) or t.get('roof:shape') == 'flat' or roof_h < 1.5
    add_prism(M_wall, poly, 0.0, eave, base_col, wall_uv=6.0, cap_color=base_col, top=flat)
    if not flat:
        r = hip_roof(poly, eave, roof_h)
        if r:
            vs, fs, uv = r
            M_roof.add(vs, fs, roof_col, uvs=uv)
        else:
            add_flat_poly(M_roof, poly, eave + 0.05, roof_col)

    if spec:
        used_landmarks.add(name)
        cx, cy = poly.centroid.x, poly.centroid.y
        landmark_pts.append((name, cx, cy, eave + roof_h))
        # Türme
        c, L = obb_pts(poly)
        longs = [0, 2] if L[0] >= L[1] else [1, 3]
        shorts = [i for i in (0, 1, 2, 3) if i not in longs]
        smids = [(c[i] + c[(i + 1) % 4]) / 2 for i in shorts]
        west = shorts[0] if smids[0][0] < smids[1][0] else shorts[1]
        p1 = c[west]; p2 = c[(west + 1) % 4]
        inset = 0.18
        def inward(pt):
            v = np.array([cx, cy]) - pt
            n = np.linalg.norm(v)
            return pt + (v / n) * (min(n, 9.0) * inset + 1.0)
        if 'tower' in spec:
            mid = inward((p1 + p2) / 2)
            add_tower(M_wall, mid[0], mid[1], spec['tower']['w'],
                      spec['tower']['h'], spec['tower']['sp'], base_col,
                      (0.30, 0.55, 0.48), kind='oct')
            add_tower(M_wall, mid[0], mid[1], spec['tower']['w']*0.72,
                      spec['tower']['h']+spec['tower']['sp']-6.0, 6.0, base_col,
                      (0.34, 0.58, 0.50), kind='oct')
        if 'twins' in spec:
            tw = spec['twins']['w']
            for pt in (p1, p2):
                q = inward(pt)
                add_tower(M_wall, q[0], q[1], tw, spec['twins']['h'], spec['twins']['sp'],
                          base_col, roof_col)
        if 'turret' in spec:
            add_tower(M_wall, cx, cy, spec['turret']['w'], spec['turret']['h'],
                      spec['turret']['sp'], base_col, roof_col)

# ------------------------------------------------ Denkmäler & Brunnen (POIs)
MON = {'Lutherdenkmal','Melanchthondenkmal','Cranachdenkmal','Johannes Bugenhagen Statue','Katharina von Bora','Marktbrunnen'}
for p in POIS:
    if p['n'] not in MON: continue
    x, y = to_xy([(p['lat'], p['lon'])])[0]
    if not (X0 <= x <= X1 and Y0 <= y <= Y1): continue
    if p['n'] == 'Lutherdenkmal':
        add_box(M_props, x, y, 3.0, 3.0, 0, 2.6, 0, (0.45,0.44,0.42))
        add_box(M_props, x, y, 1.6, 1.4, 2.6, 5.4, 0, (0.30,0.29,0.27))
    elif p['n'] == 'Melanchthondenkmal':
        add_box(M_props, x, y, 2.6, 2.6, 0, 3.2, 0, (0.44,0.43,0.41))
        add_box(M_props, x, y, 1.4, 1.2, 3.2, 5.8, 0, (0.30,0.29,0.27))
        add_tower(M_props, x, y, 1.0, 5.8, 2.2, (0.44,0.43,0.41), (0.36,0.35,0.34), kind='oct')
    elif p['n'] == 'Marktbrunnen':
        add_box(M_props, x, y, 3.2, 3.2, 0, 0.9, 0, (0.55,0.52,0.47))
        add_tower(M_props, x, y, 0.9, 1.2, 3.4, (0.55,0.52,0.47), (0.45,0.48,0.50), kind='oct')
    else:
        add_box(M_props, x, y, 1.4, 1.4, 0, 1.6, 0, (0.46,0.45,0.43))
        add_box(M_props, x, y, 0.9, 0.8, 1.6, 3.8, 0, (0.28,0.27,0.26))

# ------------------------------------------------ Grund: Straßen, Wasser, Grün, Platte
clip = clip_box()
road_w = {'motorway':12,'trunk':11,'primary':10,'secondary':9,'tertiary':8,'residential':6.0,
          'living_street':5.5,'unclassified':6,'service':3.5,'footway':2.2,'path':1.8,
          'pedestrian':6,'cycleway':2.2,'track':3,'steps':2.0}
road_cols = {'pedestrian':(0.66,0.63,0.58),'footway':(0.70,0.67,0.62),'path':(0.64,0.61,0.54),
             'service':(0.50,0.49,0.47),'track':(0.56,0.51,0.43)}
geo_roads = []
for t, pts in roads:
    cls = t.get('highway')
    w = road_w.get(cls, 5.0)
    if t.get('tunnel') in ('yes','building_passage'): continue
    try:
        ls = LineString(pts)
        g = ls.buffer(w/2, cap_style=2, join_style=2)
    except Exception:
        continue
    if g.is_empty: continue
    g = g.intersection(clip)
    if g.is_empty: continue
    col = road_cols.get(cls, (0.35,0.34,0.33))
    for gg in (g.geoms if hasattr(g, 'geoms') else [g]):
        if gg.geom_type == 'Polygon' and gg.area > 4:
            geo_roads.append((gg, col))

# Grundfläche (Pflaster/Erde) unter allem
add_flat_poly(M_ground, clip, 0.02, (0.52,0.51,0.47), uv_scale=10.0)

for p in waters:
    g = p.intersection(clip)
    for gg in (g.geoms if hasattr(g, 'geoms') else [g]):
        if gg.geom_type == 'Polygon' and gg.area > 20:
            add_flat_poly(M_ground, gg, 0.06, (0.33,0.52,0.66))

green_u = unary_union([p for p in greens]).intersection(clip) if greens else None
if green_u is not None:
    for gg in (green_u.geoms if hasattr(green_u, 'geoms') else [green_u]):
        if gg.geom_type == 'Polygon' and gg.area > 40:
            add_flat_poly(M_ground, gg, 0.04, (0.44,0.56,0.36))

# Straßen als flache Polygone (über Grund)
for gg, col in geo_roads:
    add_flat_poly(M_ground, gg, 0.05, col)

print('Grundpolygone:', M_ground.tri_count() // 2)

# ------------------------------------------------ STL / Mesh-Export
def mesh_to_trimesh(m, name):
    v = np.array(m.v, dtype=np.float64)
    f = np.array(m.f, dtype=np.int64)
    tm = trimesh.Trimesh(vertices=v, faces=f, process=False)
    tm.metadata['name'] = name
    return tm

parts = [mesh_to_trimesh(M_wall,'walls'), mesh_to_trimesh(M_roof,'roofs'), mesh_to_trimesh(M_props,'props')]
solid = trimesh.util.concatenate(parts)
print('Solid: %d Vertices, %d Faces' % (len(solid.vertices), len(solid.faces)))

# Bodenplatte
plate = trimesh.creation.box(extents=[X1-X0, 4.0, Y1-Y0])
plate.apply_translation([(X0+X1)/2, -2.0, (Y0+Y1)/2])
# Achtung: our coordinate order is (x, height, y) -> trimesh uses (x,y,z); wir behandeln y=z
scene = trimesh.util.concatenate([solid, plate])

SCALE = 0.2 / max(X1-X0, Y1-Y0)   # max. 200 mm
stl_mesh = scene.copy()
stl_mesh.apply_scale(SCALE * 1000.0)   # -> Millimeter
# Aufräumen: Dubletten verschmelzen, degenerierte Flächen und Splitter entfernen
stl_mesh.merge_vertices()
stl_mesh.update_faces(stl_mesh.nondegenerate_faces())
stl_mesh.remove_unreferenced_vertices()
_parts = stl_mesh.split(only_watertight=False)
_parts = [p for p in _parts if len(p.faces) >= 4]
stl_mesh = trimesh.util.concatenate(_parts)
print('nach Cleanup: %d Teile' % len(_parts))
stl_mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [1,0,0]))
out_stl = os.path.join(os.path.dirname(DATA), 'wittenberg_innenstadt.stl')
stl_mesh.export(out_stl)
print('STL:', out_stl, 'Maße (mm):', np.round(stl_mesh.extents, 1), 'Faces:', len(stl_mesh.faces))
json.dump({'scale': SCALE, 'extents_mm': (stl_mesh.extents*1000).tolist(),
           'bbox': [X0, Y0, X1, Y1]}, open(os.path.join(DATA,'model_meta.json'),'w'))

# ------------------------------------------------ Dump für Web-Export
def arrs(m):
    return (np.asarray(m.v, dtype=np.float32), np.asarray(m.uv, dtype=np.float32),
            (np.asarray(m.c, dtype=np.float32)*255).astype(np.uint8), np.asarray(m.f, dtype=np.uint32))

wv, wuv, wc, wf = arrs(M_wall)
rv, ruv, rc, rf = arrs(M_roof)
pv, puv, pc, pf = arrs(M_props)
gv, guv, gc, gf = arrs(M_ground)
# Gebäudeumrisse für Kollision/Minimap
polys = []
for f, poly in buildings:
    rings = [np.array(poly.exterior.coords)[:-1]] + [np.array(r.coords)[:-1] for r in poly.interiors]
    for r in rings:
        if len(r) >= 3:
            polys.append(np.asarray(r, dtype=np.float32))
pc_ = np.cumsum([len(p) for p in polys]).astype(np.uint32)
np.savez_compressed(os.path.join(DATA, 'geom.npz'),
                    wv=wv, wuv=wuv, wc=wc, wf=wf.ravel(),
                    rv=rv, ruv=ruv, rc=rc, rf=rf.ravel(),
                    pv=pv, puv=puv, pc=pc, pf=pf.ravel(),
                    gv=gv, guv=guv, gc=gc, gf=gf.ravel(),
                    poly_p=np.concatenate(polys), poly_e=pc_)
json.dump({'landmarks': [(n, float(x), float(y), float(h)) for n, x, y, h in landmark_pts],
           'info': LANDMARK_INFO,
           'bbox': [X0, Y0, X1, Y1],
           'stl_scale': SCALE,
           'stl_extents_mm': stl_mesh.extents.tolist()},
          open(os.path.join(DATA, 'web_meta.json'), 'w'))
print('Dump fertig:', len(polys), 'Ringe')
