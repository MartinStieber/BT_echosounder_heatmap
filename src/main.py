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
import os
import webbrowser
from tqdm import tqdm
import sys

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', path.dirname(path.abspath(__file__)))
    return path.join(base_path, relative_path)

def gradient_filter(data, threshold=1.8):
    data = np.array(data, dtype=np.float64)
    filtered_data = np.copy(data)

    # Calculate absolute change between neighboring values
    diffs = np.abs(np.diff(data, prepend=data[0]))

    for i in range(1, len(data)):
        if diffs[i] > threshold:
            filtered_data[i] = 0

    # Calculate absolute change between neighboring values from right to left
    diffs_reverse = np.abs(np.diff(data[::-1], prepend=data[-1]))

    for i in range(1, len(data)):
        if diffs_reverse[i] > threshold:
            filtered_data[-(i+1)] = 0

    return filtered_data.tolist()



API_KEY_mapycz = 'bftGuxvRZ3I1V3XV_kzotrTLSeA1dDjot_mFQZ25Z9Y'
API_KEY_mapbox = 'pk.eyJ1IjoibWFydGluc3RpZWJlcjEiLCJhIjoiY203OHU4dmNoMDBhejJpcXljdWNoeWNpYSJ9.DxWCzpsSUlzFRI2CPLLUZA'

pl.style.use('ggplot')

print("Welcome to the heatmap generator")
print("This program will generate a heatmap from the given BIN file")

while True:
    bin_path = input("Please, enter the path to the BIN file and press Enter to continue: ")
    if path.isfile(bin_path) and bin_path.endswith('.BIN'):
        break
    print("The file does not exist or is not a BIN file. Please, try again.")

print("\n--------------------------------------------------\n")


# ______Connect to BIN file______

mav = mavutil.mavlink_connection(bin_path)

lat = []
lon = []
sonar_ranges_raw = []


# ______Read from BIN file______

file_size = path.getsize(bin_path) / 1000000

batch_size = 1000
batch_bytes = 0

print("The BIN file is " + str(round(file_size, 2)) + " MB large.")
print("Now, reading the BIN file, this may take a while, please wait...")

pbar = tqdm(total=file_size, desc="Reading the BIN file", unit="MB", unit_scale=True)
while True:
    msg = mav.recv_match(blocking=False)
    if msg is None:
        break
    if msg.get_type() == 'DPTH':
        sonar_ranges_raw.append(msg.Depth)
        lat.append(msg.Lat)
        lon.append(msg.Lng)
    batch_bytes += len(msg.get_msgbuf())
    if batch_bytes >= batch_size:
        pbar.update(batch_bytes / 1000000)
        batch_bytes = 0

pbar.update(batch_bytes / 1000000)
pbar.close()

print("\n\nThe BIN file has been read, now processing the data...")


# ______Vykresleni hloubky v case______ DELETE IN RELEASE

fig, ax = pl.subplots()
ax.stairs(sonar_ranges_raw)
pl.show()
pl.close(fig)


# ______Gradient filter______

sonar_ranges = gradient_filter(sonar_ranges_raw)

for _ in range(70):
    sonar_ranges = gradient_filter(sonar_ranges)


# ______Median filter______

sonar_ranges = np.array(median_filter(sonar_ranges, size=15)).tolist()


# ______Vykresleni hloubky v case po medianove filtraci______ DELETE IN RELEASE

fig, ax = pl.subplots()
ax.stairs(sonar_ranges)
pl.show()
pl.close(fig)


# ______Get min and max geographic coordinates______

lat_min = min(lat)
lon_min = min(lon)
lat_max = max(lat)
lon_max = max(lon)

x = []
y = []
h = []


# ______Convert to local coordinates______

for i in range(len(lat)):
    (x_, y_, h_) = pm.geodetic2enu(lat[i], lon[i], 480, lat_min, lon_min, 480)
    x.append(x_)
    y.append(y_)
    h.append(h_)


# ______Vykresleni trasy (lokalnich souradnic)______ DELETE IN RELEASE

fig, ax = pl.subplots()
ax.plot(x, y)
pl.show()
pl.close(fig)

x_max = max(x)
y_max = max(y)


# ______Interaction with user for cell size______

x_range = str(round(max(x) - min(x), 2)) + " m"
y_range = str(round(max(y) - min(y), 2)) + " m"
print("\n--------------------------------------------------\n")
print(f"The working area is \033[1;31m{x_range}\033[0m wide in x-axis and \033[1;31m{y_range}\033[0m long in y-axis.")
while True:
    try:
        density_x = int(input("\nPlease, enter the desired density (number of cells) of the heatmap in x-axis"
                              " and press Enter to continue: "))
        density_y = int(input("Please, enter the desired density (number of cells) of the heatmap in y-axis"
                              " and press Enter to continue: "))
    except ValueError:
        print("Invalid input. Please enter a valid number.")
        continue

    if density_x <= 0 or density_y <= 0:
        print("Invalid input. Please enter a number greater than zero.")
        continue

    x_cell_range = str(round((max(x) - min(x)) / density_x, 2)) + " m"
    y_cell_range = str(round((max(y) - min(y)) / density_y, 2)) + " m"
    print(f"\nBased on your input, one cell of the heatmap will be \033[34m{x_cell_range}\033[0m wide in x-axis "
          f"and \033[34m{y_cell_range}\033[0m long in y-axis.")
    if input("Is it OK? If yes, type y. If not, type something else and press Enter to continue: ").lower() == 'y':
        break

print("\n--------------------------------------------------\n")
print("Thank you for the input, now generating the heatmap...")


# ______Insert depth values into corresponding positions in 3D array and average to 2D array______

# 3D field
heat_map_members = [[[] for _ in range(density_x)] for _ in range(density_y)]

# Values insertion
for i in range(len(x)):
    x_ = int(x[i] * (density_x - 1) / x_max)
    y_ = int(y[i] * (density_y - 1) / y_max)
    heat_map_members[y_][x_].append(sonar_ranges[i])

# Traversing through 3D array - calculating the average of the 3rd dimension - the result is a 2D array
for i in range(density_y):
    for j in range(density_x):
        if len(heat_map_members[i][j]) > 0:
            heat_map_members[i][j] = sum(heat_map_members[i][j]) / len(heat_map_members[i][j])
        else:
            heat_map_members[i][j] = 0


# ______Output directory______

output_dir = 'output'
os.makedirs(output_dir, exist_ok=True)


# ______Plot heatmap______

fig, ax = pl.subplots()
sns.heatmap(heat_map_members, cmap='hot', ax=ax, cbar=False, xticklabels=False, yticklabels=False)
ax.axis('off')
ax.invert_yaxis()
pl.savefig(os.path.join(output_dir, 'heatmap.png'), bbox_inches='tight', pad_inches=0)
pl.show()
pl.close(fig)

# Legend
fig, ax = pl.subplots(figsize=(3, 5))
norm = pl.Normalize(min(sonar_ranges), max(sonar_ranges))
sm = pl.cm.ScalarMappable(cmap='hot', norm=norm)
sm.set_array([])
cbar = fig.colorbar(sm, ax=ax)
cbar.ax.tick_params(colors='white', labelsize=12)
cbar.set_label('[m]', color='white', size=15)
cbar.ax.set_position([0.1, 0.1, 0.1, 0.8])  # [left, bottom, width, height]
pl.axis('off')
pl.savefig(os.path.join(output_dir, 'legend.png'), pad_inches=0, transparent=True)
pl.close(fig)

print("The heatmap has been generated and saved as heatmap.png, now generating the map...")


# ______Plot heatmap on map______

# Main map
m = folium.Map(location=[((lat_min + lat_max) / 2), ((lon_min + lon_max) / 2)], zoom_start=20, tiles=None, control_scale=True)

# Mapbox layer
mapbox = folium.TileLayer(f'https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{{z}}/{{x}}/{{y}}?access_token={API_KEY_mapbox}',
                 attr='© <a href="https://www.mapbox.com/about/maps">Mapbox</a> © <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> <strong><a href="https://apps.mapbox.com/feedback/" target="_blank">Improve this map</a></strong>',
                          name='Mapbox', max_zoom=22).add_to(m)

# Mapy.cz layer
mapycz = folium.TileLayer(f'https://api.mapy.cz/v1/maptiles/aerial/256/{{z}}/{{x}}/{{y}}?apikey={API_KEY_mapycz}',
                 attr='<a href="https://api.mapy.cz/copyright" target="_blank">&copy; Seznam.cz a.s. a další</a>',
                          name='Mapy.cz', max_zoom=20).add_to(m)

# Heatmap layer
raster_layers.ImageOverlay(name='Heatmap', image=os.path.join(output_dir, 'heatmap.png'), bounds=[[lat_min, lon_min], [lat_max, lon_max]], opacity=0.5).add_to(m)

# Legend layer
float_image.FloatImage('legend.png', bottom=12, left=3).add_to(m)

# Add layer control
folium.LayerControl().add_to(m)

# Save map
m.save(os.path.join(output_dir, 'heatmap.html'))
print("The map has been generated and saved as heatmap.html, now opening the map in the web browser...")

# Open map in browser
file_path = path.abspath(os.path.join(output_dir, 'heatmap.html'))
webbrowser.open(f'file://{file_path}')