#import webview
import os
import requests
from PIL import Image, ImageChops, ImageFile
from tqdm import tqdm
import io

ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None

class API:
    def foo():
        print("Bar")
        return

def get_panoid(url): return __import__('re').search(r'!1s([^!]+)', url).group(1) if __import__('re').search(r'!1s([^!]+)', url) else None

def get_tile_grid_size(zoom):
    """Calculate the number of tiles horizontally and vertically at a given zoom."""
    x_tiles = (2 ** zoom)
    y_tiles = (2 ** (zoom-1))
    return x_tiles, y_tiles

def get_all_tiles(panoid, zoom=3, save_dir=None):
    if save_dir is None:
        save_dir = f"tiles_{panoid}_z{zoom}"
    os.makedirs(save_dir, exist_ok=True)

    x_tiles, y_tiles = get_tile_grid_size(zoom)
    print(f"Attempting to download {x_tiles} x {y_tiles} tiles for pano {panoid} at zoom {zoom}...")

    tile_count = 0
    for y in tqdm(range(y_tiles), desc="Downloading rows"):
        for x in range(x_tiles):
            url = (
                f"https://streetviewpixels-pa.googleapis.com/v1/tile"
                f"?cb_client=maps_sv.tactile&panoid={panoid}"
                f"&x={x}&y={y}&zoom={zoom}&nbt=1&fover=2"
            )
            path = f"{save_dir}/tile_{x}_{y}.jpg"
            #try:
            r = requests.get(url, stream=True)
            try:
                r.raise_for_status()
            except Exception as e:
                pass
            # A more robust check for valid image content
            if len(r.content) > 1: 
                with open(path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                tile_count += 1

    if tile_count == 0:
        print("⚠️ No valid tiles found or downloaded.")
    else:
        print(f"✅ Downloaded {tile_count} tiles.")
    return save_dir, x_tiles, y_tiles

# -----------------------------------------------------------------------------

def stitch_tiles(save_dir, panoid, x_tiles, y_tiles, output_file=None, zoom=5):
    if output_file is None:
        output_file = f"{panoid}_stitched_z{zoom}.jpg"

    # Define the standard Street View tile size explicitly
    STANDARD_TILE_W = 512
    STANDARD_TILE_H = 512

    print(f"Using a standard tile size of {STANDARD_TILE_W}x{STANDARD_TILE_H} for stitching.")

    tile_matrix = [[None for _ in range(x_tiles)] for _ in range(y_tiles)]
    loaded_tile_count = 0

    # Load tiles and resize them to the standard size if necessary
    for y in range(y_tiles):
        for x in range(x_tiles):
            path = f"{save_dir}/tile_{x}_{y}.jpg"
            if os.path.exists(path):
                try:
                    tile = Image.open(path)
                    # Resize tile if its dimensions do not match the standard dimensions
                    if tile.size != (STANDARD_TILE_W, STANDARD_TILE_H):
                        print(f"Resizing tile {x},{y} from {tile.size} to {STANDARD_TILE_W}x{STANDARD_TILE_H}")
                        tile = tile.resize((STANDARD_TILE_W, STANDARD_TILE_H), Image.LANCZOS)
                    tile_matrix[y][x] = tile
                    loaded_tile_count += 1
                except Exception as e:
                    print(f"❌ Failed to open or process tile {path}: {e}")
            #else:
            #    print(f"⚠️ Tile file not found (or was skipped during download): {path}. This spot will be black.")

    if loaded_tile_count == 0:
        print("No successfully loaded tiles found after processing — aborting stitching. Final image will be black.")
        return

    # Create a new blank image for the stitched panorama
    output_img = Image.new("RGB", (STANDARD_TILE_W * x_tiles, STANDARD_TILE_H * y_tiles), (0, 0, 0))

    # Paste the processed tiles onto the output image
    for y in range(y_tiles):
        for x in range(x_tiles):
            tile = tile_matrix[y][x]
            if tile: # Only paste if the tile was successfully loaded and processed
                output_img.paste(tile, (x * STANDARD_TILE_W, y * STANDARD_TILE_H))
            # If tile is None, that area remains black as initialized, which is desired for missing tiles.

    output_img.save(output_file)
    print(f"✅ Saved stitched image: {output_file}")
    return output_file

# -----------------------------------------------------------------------------

def crop_image(img_path):
    try:
        img = Image.open(img_path)
        # Convert to RGB to ensure consistent pixel format
        if img.mode != 'RGB':
            img = img.convert('RGB')

        width, height = img.size
        print(f"Image dimensions for cropping: {width}x{height} pixels.")

        # Get all pixel data once. This is faster than `getpixel` for iterative access.
        # However, it means the entire image pixel data is loaded into a list,
        # which can still be very memory intensive for *extremely* large images.
        pixels = list(img.getdata()) 

        left_crop = (width - height) // 2
        right_crop = left_crop + height
        top_crop = 0
        bottom_crop = height

        bbox = (left_crop, top_crop, right_crop, bottom_crop)

        cropped_img = img.crop(bbox)
        
        cropped_img_path = img_path.replace(".jpg", "_cropped.jpg")
        cropped_img.save(cropped_img_path)
        print(f"✅ Cropped image saved to: {cropped_img_path}")
        return cropped_img_path

    except FileNotFoundError:
        print(f"Error: Image file not found at {img_path}")
        return None
    except Exception as e:
        print(f"An error occurred during cropping: {e}")
        return None

# -----------------------------------------------------------------------------

def main():
    urls = [
        r"https://www.google.com/maps/@42.3644583,-71.0830152,3a,75y,97.46h,78.09t/data=!3m7!1e1!3m5!1s-2k5oygFKPkYSwTNXB4fpw!2e0!6shttps:%2F%2Fstreetviewpixels-pa.googleapis.com%2Fv1%2Fthumbnail%3Fcb_client%3Dmaps_sv.tactile%26w%3D900%26h%3D600%26pitch%3D11.913985311868203%26panoid%3D-2k5oygFKPkYSwTNXB4fpw%26yaw%3D97.456470297262!7i16384!8i8192?entry=ttu&g_ep=EgoyMDI1MDcxNi4wIKXMDSoASAFQAw%3D%3D",
        #r"https://www.google.com/maps/@42.3644456,-71.0828907,3a,75y,97.46h,78.09t/data=!3m7!1e1!3m5!1sE34uUND3nKb8vPG2hkxpMA!2e0!6shttps:%2F%2Fstreetviewpixels-pa.googleapis.com%2Fv1%2Fthumbnail%3Fcb_client%3Dmaps_sv.tactile%26w%3D900%26h%3D600%26pitch%3D11.913985311868203%26panoid%3DE34uUND3nKb8vPG2hkxpMA%26yaw%3D97.456470297262!7i16384!8i8192?entry=ttu&g_ep=EgoyMDI1MDcxNi4wIKXMDSoASAFQAw%3D%3D",
        #r"https://www.google.com/maps/@42.3644213,-71.0827625,3a,75y,97.46h,78.09t/data=!3m7!1e1!3m5!1svF4ma2ROszvpPE89pUQqyg!2e0!6shttps:%2F%2Fstreetviewpixels-pa.googleapis.com%2Fv1%2Fthumbnail%3Fcb_client%3Dmaps_sv.tactile%26w%3D900%26h%3D600%26pitch%3D11.913985311868203%26panoid%3DvF4ma2ROszvpPE89pUQqyg%26yaw%3D97.456470297262!7i16384!8i8192?entry=ttu&g_ep=EgoyMDI1MDcxNi4wIKXMDSoASAFQAw%3D%3D",
        #r"https://www.google.com/maps/@42.3644031,-71.0826425,3a,75y,97.46h,78.09t/data=!3m7!1e1!3m5!1sn67_l2_T5IrgKIMh89WIUA!2e0!6shttps:%2F%2Fstreetviewpixels-pa.googleapis.com%2Fv1%2Fthumbnail%3Fcb_client%3Dmaps_sv.tactile%26w%3D900%26h%3D600%26pitch%3D11.913985311868203%26panoid%3Dn67_l2_T5IrgKIMh89WIUA%26yaw%3D97.456470297262!7i16384!8i8192?entry=ttu&g_ep=EgoyMDI1MDcxNi4wIKXMDSoASAFQAw%3D%3D",
        #r"https://www.google.com/maps/@42.3643889,-71.082529,3a,75y,97.46h,78.09t/data=!3m7!1e1!3m5!1sgKyvg0ZjEltToNn7V0o4SQ!2e0!6shttps:%2F%2Fstreetviewpixels-pa.googleapis.com%2Fv1%2Fthumbnail%3Fcb_client%3Dmaps_sv.tactile%26w%3D900%26h%3D600%26pitch%3D11.913985311868203%26panoid%3DgKyvg0ZjEltToNn7V0o4SQ%26yaw%3D97.456470297262!7i16384!8i8192?entry=ttu&g_ep=EgoyMDI1MDcxNi4wIKXMDSoASAFQAw%3D%3D",
        #r"https://www.google.com/maps/@42.3643754,-71.0824088,3a,75y,97.46h,78.09t/data=!3m7!1e1!3m5!1s2YXFqWxM2rDVAo8irijwuQ!2e0!6shttps:%2F%2Fstreetviewpixels-pa.googleapis.com%2Fv1%2Fthumbnail%3Fcb_client%3Dmaps_sv.tactile%26w%3D900%26h%3D600%26pitch%3D11.913985311868203%26panoid%3D2YXFqWxM2rDVAo8irijwuQ%26yaw%3D97.456470297262!7i16384!8i8192?entry=ttu&g_ep=EgoyMDI1MDcxNi4wIKXMDSoASAFQAw%3D%3D",
        #r"https://www.google.com/maps/@42.3643629,-71.0822918,3a,75y,97.46h,78.09t/data=!3m7!1e1!3m5!1sR6a_ybUvwA-2z0uobvAjJg!2e0!6shttps:%2F%2Fstreetviewpixels-pa.googleapis.com%2Fv1%2Fthumbnail%3Fcb_client%3Dmaps_sv.tactile%26w%3D900%26h%3D600%26pitch%3D11.913985311868203%26panoid%3DR6a_ybUvwA-2z0uobvAjJg%26yaw%3D97.456470297262!7i16384!8i8192?entry=ttu&g_ep=EgoyMDI1MDcxNi4wIKXMDSoASAFQAw%3D%3D",
        #r"https://www.google.com/maps/@42.3643508,-71.0821734,3a,75y,97.46h,78.09t/data=!3m7!1e1!3m5!1s0uXNg7QkwnpGO8IKlA-PFQ!2e0!6shttps:%2F%2Fstreetviewpixels-pa.googleapis.com%2Fv1%2Fthumbnail%3Fcb_client%3Dmaps_sv.tactile%26w%3D900%26h%3D600%26pitch%3D11.913985311868203%26panoid%3D0uXNg7QkwnpGO8IKlA-PFQ%26yaw%3D97.456470297262!7i16384!8i8192?entry=ttu&g_ep=EgoyMDI1MDcxNi4wIKXMDSoASAFQAw%3D%3D",
    ]

    #api = API()
    #webview.create_window("Hello World", '/index.hmtl', js_api=api)
    #webview.start()

    panoids = [get_panoid(url) for url in urls]
    final_img = None
    for panoid in panoids:
        a, b, c = get_all_tiles(panoid, zoom=5)
        final_img = stitch_tiles(a, panoid, b, c, zoom=5)

    final_img = crop_image(final_img)

if __name__ == "__main__":
    main()