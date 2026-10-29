import osmium, json
from collections import Counter, defaultdict
S,W,N,E = 51.8570, 12.6290, 51.8760, 12.6600
KEEP={'building','building:part','highway','railway','natural','waterway','leisure','landuse','amenity','historic','tourism','barrier','area:highway','man_made','place','boundary','shop','religion','name','height','building:levels','roof:shape','roof:height','roof:colour','building:colour','min_height','layer','tunnel','bridge','width','area'}
SKIP={'building':{'roof','no','garage','garages','shed','carport','hut','garage_boxes','greenhouse'},
 'highway':{'proposed','construction','abandoned','platform','elevator','steps','corridor'},
 'natural':{'tree','tree_row','peak','scrub'},
 'barrier':{'hedge','fence','retaining_wall','guard_rail'},
 'landuse':{'farmland','meadow','orchard','vineyard','allotments'},
 'railway':{'rail','light_rail','platform','tram','subway'}}

nodes={}; ways={}; feats=[]; rels=[]
class H(osmium.SimpleHandler):
    def node(self,n):
        nodes[n.id]=(round(n.location.lat,7),round(n.location.lon,7))
    def way(self,w):
        try: c=[nodes[r.ref] for r in w.nodes]
        except KeyError: return
        ways[w.id]=c
        tags={}
        for k,v in w.tags:
            if k in KEEP: tags[k]=v
        if not tags: return
        for k,v in tags.items():
            if k in SKIP and v in SKIP[k]: return
        if not any(k in tags for k in ('building','highway','natural','waterway','leisure','landuse','area:highway','barrier','railway','man_made')): return
        if len(c)<2: return
        lats=[p[0] for p in c]; lons=[p[1] for p in c]
        if max(lats)<S or min(lats)>N or max(lons)<W or min(lons)>E: return
        feats.append({'id':'w%d'%w.id,'t':tags,'n':tags.get('name'),'c':c})
    def relation(self,r):
        tags={}
        for k,v in r.tags:
            if k in KEEP: tags[k]=v
        if 'building' not in tags and 'landuse' not in tags: return
        rels.append({'id':'r%d'%r.id,'t':tags,'n':tags.get('name'),
                     'outer':[(m.ref,m.role) for m in r.members if m.type=='w' and m.role in ('outer','')],
                     'inner':[(m.ref,m.role) for m in r.members if m.type=='w' and m.role=='inner']})
h=H(); h.apply_file('data/wb.osm.pbf', locations=True)
print("ways",len(feats),"buildings",sum(1 for f in feats if 'building' in f['t']),"rels",len(rels))

def ring(ids):
    segs=[ways[i] for i in ids if i in ways and len(ways[i])>=2]
    if not segs: return None
    out=list(segs[0]); used={0}
    for _ in range(len(segs)+3):
        if out[0]==out[-1]: break
        for j,s in enumerate(segs):
            if j in used: continue
            if s[0]==out[-1]: out+=s[1:]; used.add(j); break
            if s[-1]==out[-1]: out+=s[::-1][1:]; used.add(j); break
    if out[0]!=out[-1]: out.append(out[0])
    return out

nrel=0
for r in rels:
    o=ring([i for i,_ in r['outer']])
    if not o or len(o)<4: continue
    lats=[p[0] for p in o]; lons=[p[1] for p in o]
    if max(lats)<S or min(lats)>N or max(lons)<W or min(lons)>E: continue
    inn=[]
    for i,_ in r['inner']:
        rr=ring([i])
        if rr and len(rr)>3: inn.append(rr)
    feats.append({'id':r['id'],'t':r['t'],'n':r['n'],'c':o,'inner':inn})
    nrel+=1
print("relation features",nrel,"total",len(feats))
json.dump(feats,open('data/features.json','w'))
named=[f for f in feats if f['n'] and ('building' in f['t'] or f['t'].get('historic') or f['t'].get('tourism'))]
print("named",len(named))
for f in sorted(named,key=lambda x:x['n']):
    print(" -",f['n'],"|",f['t'].get('building',''),f['t'].get('historic',''),f['t'].get('tourism',''),"h=",f['t'].get('height',''),f['t'].get('building:levels',''))
