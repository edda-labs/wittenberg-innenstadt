Lutherstadt Wittenberg – Innenstadt in 3D
========================================

Projektstand: Oktober 2026
Ausschnitt: ca. 1,56 km (O–W) × 1,08 km (N–S), 1.644 Gebäude

Dateien
-------
wittenberg_innenstadt_3d.html   Fertige Webseite (alles eingebettet, offline lauffähig)
wittenberg_innenstadt.stl       Druckmodell, 204 × 143 × 12 mm (Maßstab ca. 1:7 900)
preview_overview.png            Bild: Übersicht
preview_street.png              Bild: Straßenansicht am Markt

Bedienung der Webseite
----------------------
Rundflug    Ziehen = drehen, Scrollen = zoomen, Denkmal anklicken = Info
Street View WASD / Pfeiltasten = gehen, Maus = umsehen, Shift = rennen, ESC = beenden
Rundgang    automatischer Drohnenflug über die Straßen (Markt → Schlosskirche → Lutherhaus)
Denkmäler   Liste mit 15 Bauwerken, Klick springt hin
STL ↓       lädt das Druckmodell direkt herunter
Mobil       links Joystick, rechts umsehen, Minimap-Klick = Teleport

Datenbasis
----------
Gebäudeumrisse, Straßen, Gewässer, Grünflächen und Denkmal-Standorte:
OpenStreetMap, Extrakt Sachsen-Anhalt von Geofabrik (download.geofabrik.de).
Ausschnitt mit osmium-tool geschnitten (data/wb.osm.pbf).

Höhen: OSM-Tags (height, building:levels) wo vorhanden, sonst typologische
Schätzung nach Gebäudetyp (meist 3–4 Geschosse). Turmhöhen nach Literatur:
Schlosskirche 88 m, Stadtkirche St. Marien 60 m.

Dächer: algorithmisch erzeugtes Offset-Lofting (Walm-/Hüftdächer), keine
Katasterdaten. Fassaden und Fenster sind eine prozedurale Textur.

Denkmäler (Lutherdenkmal, Melanchthondenkmal, Cranachdenkmal, Bugenhagen- und
Katharina-von-Bora-Statue, Marktbrunnen) sind als Podest + Figur stark
vereinfacht.

Das Modell ist für Anschauung, Lehre und 3D-Druck gedacht – nicht für Vermessung.

Neu bauen
---------
Voraussetzungen: Python 3.11, osmium-tool (apt), venv mit
trimesh, shapely, numpy-stl, mapbox-earcut, networkx, scipy

1. Osmium-Extrakt ziehen (nur einmal nötig):
   curl -L -o data/sa.osm.pbf https://download.geofabrik.de/europe/germany/sachsen-anhalt-latest.osm.pbf
   osmium extract -b 12.6290,51.8570,12.6600,51.8760 --strategy=smart -o data/wb.osm.pbf data/sa.osm.pbf

2. OSM-Daten einlesen:
   python extract5.py      -> data/features.json
   python nodes_poi.py     -> data/pois.json

3. Geometrie + STL erzeugen:
   python build_scene.py   -> wittenberg_innenstadt.stl, data/geom.npz, data/web_meta.json

4. Rundgang-Route berechnen:
   python make_tour.py     -> data/tour.json

5. Webseite bauen:
   python export_web.py    -> wittenberg_innenstadt_3d.html

Anpassen
--------
Ausschnitt:      X0/X1/Y0/Y1 in build_model.py (lokale Meter, Ursprung Markt)
Höhen/Türme:     Dict LM in build_scene.py
Infotexte:       Liste LANDMARK_INFO in build_scene.py
Farben:          PLASTER/ROOF in build_model.py
Druckmaßstab:    SCALE in build_scene.py (aktuell 0,2 m / Modellbreite)

Drucken
-------
0,4-mm-Düse, 0,12 mm Schicht, kein Support nötig, Grundplatte ist enthalten.
Das STL besteht aus vielen geschlossenen Einzelkörpern – im Slicer einmal
"reparieren/vereinigen" lassen.
