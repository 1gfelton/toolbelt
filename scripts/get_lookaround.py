import pillow_heif as ph
from PIL import Image
from streetlevel import lookaround
import numpy as np
from tqdm import tqdm
import math 
import sys
import os

# --- Start: get target coords and number from cmd arguments

if len(sys.argv) < 3:
    print("Usage: python get_lookaround.py <latitude> <longitude> [num_panos]")
    sys.exit(1)

try:
    target_lat = float(sys.argv[1])
    target_lon = float(sys.argv[2])
    num_panos = int(sys.argv[3]) 
    zoom = int(sys.argv[4]) if len(sys.argv) > 4 else 2
except ValueError:
    print("Error: Latitude and longitude must be valid numbers, num_panos must be a valid integer.")
    sys.exit(1)

# Validate num_panos
if num_panos < 1 or num_panos > 500:
    print("Error: Number of panoramas must be between 1 and 50.")
    sys.exit(1)

# --- End: Get target coordinates and number from cmd arguments

# --- Define Output Dir

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "output")

if not os.path.exists(out_dir):
    os.makedirs(out_dir)

# --- Initialize authentication and zoom level

auth = lookaround.Authenticator()
#zoom = 0

print(f"Searching for up to {num_panos} panorama(s) near {target_lat}, {target_lon}")

# Get initial coverage tile
initial_tile = lookaround.get_coverage_tile_by_latlon(target_lat, target_lon)

if not initial_tile:
    print(f"No coverage tile found for initial coordinates {target_lat}, {target_lon}.", file=sys.stderr)
    sys.exit(1)

initial_tile_x = initial_tile.x
initial_tile_y = initial_tile.y

# Expand search area based on number of requested panoramas
# For more panoramas, we need to search more tiles
search_radius = max(1, math.ceil(math.sqrt(num_panos / 4)))  # Adaptive search radius

tile_coords_to_check = set()
for dx in range(-search_radius, search_radius + 1):
    for dy in range(-search_radius, search_radius + 1):
        tile_coords_to_check.add((initial_tile_x + dx, initial_tile_y + dy))

all_panos = []
print(f"Fetching panoramas from {len(tile_coords_to_check)} coverage tiles (search radius: {search_radius})...")

for tile_x, tile_y in tqdm(tile_coords_to_check, desc="Fetching tiles", file=sys.stderr):
    try:
        tile = lookaround.get_coverage_tile(tile_x, tile_y)
        if tile and tile.panos:
            all_panos.extend(tile.panos)
    except Exception as e:
        print(f"Could not fetch tile ({tile_x}, {tile_y}): {e}", file=sys.stderr)
        continue

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

for pano_idx, pano in enumerate(selected_panos, 1):
    print(f"\nProcessing panorama {pano_idx}/{len(selected_panos)}: {pano.id}")
    
    faces = []
    face_download_success = True
    
    for face_idx in tqdm(range(0, 6), desc=f"Downloading pano {pano_idx} faces", file=sys.stderr):
        try:
            face_heic = lookaround.get_panorama_face(pano, face_idx, zoom, auth)
            face = ph.open_heif(face_heic, convert_hdr_to_8bit=False, bgr_mode=False)
            np_arr = np.asarray(face)
            faces.append(Image.fromarray(np_arr))
        except Exception as e:
            print(f"Error downloading or processing face {face_idx} for pano {pano.id}: {e}", file=sys.stderr)
            face_download_success = False
            break

    if face_download_success and len(faces) == 6:
        try:
            result = lookaround.to_equirectangular(faces, pano.camera_metadata)
            output_filename = os.path.join(out_dir, f"{pano.id}_{zoom}.jpg")
            result.save(output_filename, options={"quality": 100})
            print(f"Saved equirectangular panorama: {output_filename}")
            successful_downloads += 1
        except Exception as e:
            print(f"Error creating or saving equirectangular panorama for pano {pano.id}: {e}", file=sys.stderr)
            failed_downloads += 1
    else:
        print(f"Could not download all 6 faces for pano {pano.id}. Skipping equirectangular conversion.", file=sys.stderr)
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