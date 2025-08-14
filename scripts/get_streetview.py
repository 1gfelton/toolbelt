import pillow_heif as ph
from PIL import Image
from streetlevel import streetview
import numpy as np
from tqdm import tqdm
import math 
import sys
import os

# --- Start: get target coords and number from cmd arguments
print(f"{'#'*20}\tCurrently Using Google Streetview Data")
if len(sys.argv) < 3:
    print("Usage: python get_streetview.py <latitude> <longitude> [num_panos]")
    sys.exit(1)

try:
    target_lat = float(sys.argv[1])
    target_lon = float(sys.argv[2])
    out_dir = str(sys.argv[3]) 
    num_panos = int(sys.argv[4]) 
    zoom = int(sys.argv[5]) if len(sys.argv) > 4 else 2
except ValueError:
    print("Error: Latitude and longitude must be valid numbers, num_panos must be a valid integer.")
    sys.exit(1)

# Validate num_panos
if num_panos < 1 or num_panos > 500:
    print("Error: Number of panoramas must be between 1 and 50.")
    sys.exit(1)

# --- End: Get target coordinates and number from cmd arguments

# --- Define Output Dir
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "output") if out_dir == None else out_dir
os.makedirs(out_dir, exist_ok=True)

print(f"Searching for up to {num_panos} panorama(s) near {target_lat}, {target_lon}")

# Get initial coverage tile
initial_tile = streetview.get_coverage_tile_by_latlon(target_lat, target_lon)

if not initial_tile:
    print(f"No coverage tile found for initial coordinates {target_lat}, {target_lon}.", file=sys.stderr)
    sys.exit(1)
all_panos = []

print(f"Fetching panoramas...")

if initial_tile:
    for pano_idx, pano in tqdm(enumerate(initial_tile)):
        all_panos.append(pano)

if not all_panos:
    print("No panoramas found in the selected coverage tiles.", file=sys.stderr)
    sys.exit(1)

print(f"Found {len(all_panos)} total panorama(s) in search area")

def distance(lat1, lon1, lat2, lon2):
    """Calculate simple Euclidean distance between two coordinates"""
    return math.sqrt(((lat1 - lat2) ** 2) + ((lon1 - lon2) ** 2))

# Sort panoramas by distance and take the closest ones
sorted_panos = sorted(all_panos, key=lambda p: distance(p.lat, p.lon, target_lat, target_lon))
selected_panos = sorted_panos[:num_panos]

print(f"\nSelected {len(selected_panos)} closest panorama(s):")
for i, pano in enumerate(selected_panos, 1):
    dist = distance(pano.lat, pano.lon, target_lat, target_lon)
    print(f"  {i}. Pano {pano.id} at {pano.lat}, {pano.lon} (distance: {dist:.8f}) - {pano.date}")

# Process each selected panorama
successful_downloads = 0
failed_downloads = 0

for pano_idx, pano in tqdm(enumerate(selected_panos, 1)):
    print(f"\nProcessing panorama {pano_idx}/{len(selected_panos)}: {pano.id}")

    panos = []
    try:
        result = streetview.find_panorama_by_id(pano.id)
        if result:
            print(f"Successfully got pano: {result.id}")
            img = streetview.get_panorama(result)
            panos.append(result)
            out_file = os.path.join(out_dir, f"google_{pano.id}_{zoom}.jpg")
            img.save(out_file, options = {"quality":100})
            print(f"Saved streetview panorama: {out_file}")
            successful_downloads += 1
    except Exception as e:
        print(f"Failed to get pano at {pano.lat}, {pano.lon}: {e}")
        failed_downloads += 1

# Summary
print(f"\n=== Processing Complete ===")
print(f"Successfully processed: {successful_downloads} panorama(s)")
print(f"Failed to process: {failed_downloads} panorama(s)")
print(f"Total requested: {num_panos}")

if successful_downloads == 0:
    print("No panoramas were successfully processed.", file=sys.stderr)
    sys.exit(1)
elif failed_downloads > 0:
    print(f"Warning: {failed_downloads} panorama(s) failed to process.", file=sys.stderr)
