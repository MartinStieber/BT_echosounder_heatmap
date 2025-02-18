#!/usr/bin/env python3

from pymavlink import mavutil
import matplotlib.pyplot as pl
import pymap3d as pm
from scipy.ndimage import median_filter
import seaborn as sns
import folium
import numpy as np
from folium.plugins import float_image
from folium import raster_layers
from os import path
import webbrowser

#density_x = 30
#density_y = 30

API_KEY_mapycz = 'bftGuxvRZ3I1V3XV_kzotrTLSeA1dDjot_mFQZ25Z9Y'

pl.style.use('ggplot')

#path = "/home/martin/PIXHAWK_logs/00000004.BIN"

print("Welcome in the heatmap generator")
print("This program will generate a heatmap from the given BIN file")

while True:
    bin_path = input("Please, enter the path to the BIN file and press Enter to continue: ")
    if path.isfile(bin_path) and bin_path.endswith('.BIN'):
        break
    print("The file does not exist or is not a BIN file. Please, try again.")

density_x = int(input("Please, enter the number of columns in the heatmap and press Enter to continue: "))
density_y = int(input("Please, enter the number of rows in the heatmap and press Enter to continue: "))

print("\n--------------------------------------------------\n")

print("Now, reading the BIN file, this may take a while, please wait...")

# ______Pripojeni k BIN souboru______
mav = mavutil.mavlink_connection(bin_path)

timestamps = []
lat_raw = []
lon_raw = []
sonar_ranges_raw = []

# ______Cteni z BIN souboru______

while True:
    msg = mav.recv_match(blocking=False)
    if msg is None:
        break
    if msg.get_type() == 'DPTH':
        timestamps.append(msg.TimeUS)
        sonar_ranges_raw.append(msg.Depth)
        lat_raw.append(msg.Lat)
        lon_raw.append(msg.Lng)

print("The BIN file has been read, now processing the data and generating the heatmap...")


# ______Orez velkych hodnot______

for i in range(len(sonar_ranges_raw)):
    if sonar_ranges_raw[i] > 5:
        sonar_ranges_raw[i] = 5


# ______Vykresleni hloubky v case______

fig, ax = pl.subplots()
ax.stairs(sonar_ranges_raw)
pl.show()
pl.close(fig)


# ______Vyrez______(Pouze pro beta)

lat = lat_raw[12000:36000]
lon = lon_raw[12000:36000]
sonar_ranges_raw = sonar_ranges_raw[12000:36000]


# ______Medianova filtrace______

sonar_ranges = np.array(median_filter(sonar_ranges_raw, size=30)).tolist()


# ______Vykresleni hloubky v case po medianove filtraci______

fig, ax = pl.subplots()
ax.stairs(sonar_ranges)
pl.show()
pl.close(fig)


# ______Vycteni minimalni a maximalni hodnoty zemepisnych souradnic______

lat_min = min(lat)
lon_min = min(lon)
lat_max = max(lat)
lon_max = max(lon)

x = []
y = []
h = []


# ______Prevod na lokalni souradnice______

for i in range(len(lat)):
    (x_, y_, h_) = pm.geodetic2enu(lat[i], lon[i], 480, lat_min, lon_min, 480)
    x.append(x_)
    y.append(y_)
    h.append(h_)


# ______Vykresleni trasy (lokalnich souradnic)______

fig, ax = pl.subplots()
ax.plot(x, y)
pl.show()
pl.close(fig)

x_max = max(x)
y_max = max(y)


# ______Vlozeni hodnot hloubky na korespondujici umisteni ve 3D poli a prumerovani na 2D pole______

# Definice 3D pole
heat_map_members = [[[] for _ in range(density_x)] for _ in range(density_y)]

# Vlozeni hodnot
for i in range(len(x)):
    x_ = int(x[i] * (density_x - 1) / x_max)
    y_ = int(y[i] * (density_y - 1) / y_max)
    heat_map_members[y_][x_].append(sonar_ranges[i])

# Prumerovani pomoci traverzovani pres 3D pole - vypocet prumeru 3 dimenze - vysledkem je 2D pole
for i in range(density_y):
    for j in range(density_x):
        if len(heat_map_members[i][j]) > 0:
            heat_map_members[i][j] = sum(heat_map_members[i][j]) / len(heat_map_members[i][j])
        else:
            heat_map_members[i][j] = 0


# ______Vykresleni heatmapy______

fig, ax = pl.subplots()
#mask = np.array(heat_map_members) == 0 # maskovani nulovych hodnot
sns.heatmap(heat_map_members, cmap='hot', ax=ax, cbar=False, xticklabels=False, yticklabels=False)
ax.axis('off')
ax.invert_yaxis()
pl.savefig('heatmap.png', bbox_inches='tight', pad_inches=0)
pl.show()
pl.close(fig)

#legenda
fig, ax = pl.subplots(figsize=(2, 6))
norm = pl.Normalize(min(sonar_ranges), max(sonar_ranges))
sm = pl.cm.ScalarMappable(cmap='hot', norm=norm)
sm.set_array([])
fig.colorbar(sm, ax=ax)
pl.axis('off')
pl.savefig('legend.png', pad_inches=0)
pl.close(fig)

print("The heatmap has been generated and saved as heatmap.png, now generating the map...")


# ______Vykresleni heatmapy na mape______

# Hlavni mapa
m = folium.Map(location=[((lat_min + lat_max) / 2), ((lon_min + lon_max) / 2)], zoom_start=20, tiles=None)

# Podklad Mapbox
folium.TileLayer(f'https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{{z}}/{{x}}/{{y}}?access_token=pk.eyJ1IjoibWFydGluc3RpZWJlcjEiLCJhIjoiY203OHU4dmNoMDBhejJpcXljdWNoeWNpYSJ9.DxWCzpsSUlzFRI2CPLLUZA',
                 attr='Mapbox', name='Satellite', max_zoom=22).add_to(m)

# Podklad Mapy.cz
folium.TileLayer(f'https://api.mapy.cz/v1/maptiles/aerial/256/{{z}}/{{x}}/{{y}}?apikey={API_KEY_mapycz}',
                 attr='<a href="https://api.mapy.cz/copyright" target="_blank">&copy; Seznam.cz a.s. a další</a>', max_zoom=20).add_to(m)

# Heatmapa
raster_layers.ImageOverlay(name='Heatmap', image='heatmap.png', bounds=[[lat_min, lon_min], [lat_max, lon_max]], opacity=0.5).add_to(m)

# Legenda
float_image.FloatImage('legend.png', bottom=10, left=90).add_to(m)

# Pridani volby vrstev
folium.LayerControl().add_to(m)

# Ulozeni mapy
m.save('heatmap.html')
print("The map has been generated and saved as heatmap.html, now opening the map in the web browser...")

# Otevreni mapy v prohlizeci
webbrowser.open('heatmap.html')