import osmium, json
S,W,N,E = 51.8570, 12.6290, 51.8760, 12.6600
pois=[]
class H(osmium.SimpleHandler):
    def node(self,n):
        t={k:v for k,v in n.tags}
        if not t: return
        if not any(k in t for k in ('historic','tourism','amenity','memorial','man_made')): return
        if not (S<=n.location.lat<=N and W<=n.location.lon<=E): return
        pois.append({'id':n.id,'lat':round(n.location.lat,7),'lon':round(n.location.lon,7),
                     'n':t.get('name'),'t':{k:v for k,v in t.items() if k in ('historic','tourism','amenity','memorial','man_made','height','inscription')}})
H().apply_file('data/wb.osm.pbf', locations=True)
print(len(pois))
for p in pois:
    if p['n']: print(" -",p['n'],p['t'])
json.dump(pois,open('data/pois.json','w'))
