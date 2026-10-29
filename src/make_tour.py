import json, math, numpy as np, networkx as nx
from shapely.geometry import LineString, Point, Polygon
F=json.load(open('data/features.json'))
lat0,lon0=51.86640,12.64720
ky=110574.0; kx=111320.0*math.cos(math.radians(lat0))
def xy(c): return [((p[1]-lon0)*kx,(p[0]-lat0)*ky) for p in c]
GOOD={'pedestrian','residential','living_street','unclassified','tertiary'}
G=nx.Graph()
for f in F:
    if 'highway' not in f['t'] or f['t']['highway'] not in GOOD: continue
    p=xy(f['c'])
    for a,b in zip(p,p[1:]):
        if math.dist(a,b)>0.5 and abs(a[0])<900 and abs(a[1])<700 and -600<a[1]<700:
            G.add_edge((round(a[0],1),round(a[1],1)),(round(b[0],1),round(b[1],1)),
                       weight=math.dist(a,b))
print("graph",G.number_of_nodes(),G.number_of_edges())
nodes=list(G.nodes)
def nearest(pt):
    return min(nodes,key=lambda n: math.dist(n,pt))
stops=[(-250,45),(-610,8),(-250,45),(367,-240),(-250,45)]
path=[]
for a,b in zip(stops,stops[1:]):
    na,nb=nearest(a),nearest(b)
    seg=nx.shortest_path(G,na,nb,weight='weight')
    if path: seg=seg[1:]
    path+=seg
print("path nodes",len(path))
# glätten + auf 2 m abtasten
ls=LineString(path).simplify(1.0)
pts=[]
for i in range(len(ls.coords)-1):
    a=np.array(ls.coords[i]); b=np.array(ls.coords[i+1])
    d=np.linalg.norm(b-a); n=max(1,int(d/2.0))
    for k in range(n):
        pts.append(tuple(a+(b-a)*k/n))
pts.append(ls.coords[-1])
print("tour points",len(pts))
# Kollisionscheck
blds=[Polygon(xy(f['c'])) for f in F if 'building' in f['t'] and f['t'].get('building') not in ('roof','no')]
bad=[]
for p in pts:
    q=Point(p)
    if any(b.contains(q) for b in blds): bad.append(p)
print("Punkte in Gebäuden:",len(bad))
good=[p for p in pts if p not in bad]
json.dump({'tour':[[round(x,1),round(y,1)] for x,y in good],'bad':len(bad)},open('data/tour.json','w'))
print('gefiltert:',len(good))
