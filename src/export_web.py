import json, os, base64, gzip, numpy as np
D='/root/wittenberg3d'
G=np.load(os.path.join(D,'data','geom.npz'))
meta=json.load(open(os.path.join(D,'data','web_meta.json')))
tour=json.load(open(os.path.join(D,'data','tour.json')))

def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode('ascii')

def pack(p,uv,c,f):
    return {'p':b64(G[p]),'uv':b64(G[uv]),'c':b64(G[c]),'i':b64(G[f])}

payload={
 'meta':{'bbox':meta['bbox'],'stl_scale':meta['stl_scale'],'stl_mm':meta['stl_extents_mm']},
 'walls':pack('wv','wuv','wc','wf'),
 'roofs':pack('rv','ruv','rc','rf'),
 'props':pack('pv','puv','pc','pf'),
 'ground':pack('gv','guv','gc','gf'),
 'polys':{'p':b64(G['poly_p'].astype(np.float32)),'e':b64(G['poly_e'].astype(np.uint32))},
 'landmarks':meta['landmarks'],
 'info':meta['info'],
 'tour':tour['tour'],
 'start':[-250.0, 45.0, 3.05],
}
raw=json.dumps(payload,separators=(',',':')).encode()
gz=gzip.compress(raw,9)
print('payload raw MB',round(len(raw)/1e6,2),'gz MB',round(len(gz)/1e6,2))
P=base64.b64encode(gz).decode()

stl=open(os.path.join(D,'wittenberg_innenstadt.stl'),'rb').read()
sgz=gzip.compress(stl,9)
print('stl MB',round(len(stl)/1e6,2),'gz MB',round(len(sgz)/1e6,2))
S=base64.b64encode(sgz).decode()

three=base64.b64encode(open(os.path.join(D,'data','three.min.js'),'rb').read()).decode()
html=open(os.path.join(D,'template.html')).read()
html=html.replace('__PAYLOAD__',P).replace('__STL__',S).replace('__THREE__',three)
out=os.path.join(D,'wittenberg_innenstadt_3d.html')
open(out,'w').write(html)
print('HTML MB',round(os.path.getsize(out)/1e6,2))
