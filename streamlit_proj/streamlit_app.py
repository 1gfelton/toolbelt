import streamlit as st
import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile
import uuid
import atexit
import shutil
import zipfile
from datetime import datetime
import time
import math
from tqdm import tqdm

# Import heavy modules once at startup
try:
    import cv2
    import torch
    import torchvision
    import folium
    from streamlit_folium import st_folium
    
    # Import script modules
    import pillow_heif as ph
    from PIL import Image
    from streetlevel import lookaround
    import py360convert
    
except ImportError as e:
    st.error(f"Missing required dependencies: {e}")

# Import script functions
def import_script_functions():
    """Import functions from script files"""
    try:
        # Add scripts directory to path
        app_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(app_dir)
        scripts_dir = os.path.join(project_root, "scripts")
        sys.path.insert(0, scripts_dir)
        
        return scripts_dir
    except Exception as e:
        st.error(f"Failed to import script functions: {e}")
        return None

def get_lookaround_panoramas(target_lat, target_lon, out_dir, num_panos, zoom, progress_callback=None):
    """
    Download panoramas from Apple Lookaround
    
    Args:
        target_lat: Target latitude
        target_lon: Target longitude  
        out_dir: Output directory
        num_panos: Number of panoramas to download
        zoom: Zoom level
        progress_callback: Function to call with progress updates
    
    Returns:
        dict: {"success": bool, "output": str, "downloaded_files": list}
    """
    try:
        # Validate inputs
        if num_panos < 1 or num_panos > 500:
            return {"success": False, "output": "Number of panoramas must be between 1 and 500.", "downloaded_files": []}
        
        os.makedirs(out_dir, exist_ok=True)
        
        if progress_callback:
            progress_callback(f"Searching for up to {num_panos} panorama(s) near {target_lat}, {target_lon}")
        
        # Initialize authentication
        auth = lookaround.Authenticator()
        
        # Get initial coverage tile
        initial_tile = lookaround.get_coverage_tile_by_latlon(target_lat, target_lon)
        
        if not initial_tile:
            return {"success": False, "output": f"No coverage tile found for coordinates {target_lat}, {target_lon}.", "downloaded_files": []}
        
        initial_tile_x = initial_tile.x
        initial_tile_y = initial_tile.y
        
        # Expand search area based on number of requested panoramas
        search_radius = max(1, math.ceil(math.sqrt(num_panos / 4)))
        
        tile_coords_to_check = set()
        for dx in range(-search_radius, search_radius + 1):
            for dy in range(-search_radius, search_radius + 1):
                tile_coords_to_check.add((initial_tile_x + dx, initial_tile_y + dy))
        
        all_panos = []
        if progress_callback:
            progress_callback(f"Fetching panoramas from {len(tile_coords_to_check)} coverage tiles...")
        
        for tile_x, tile_y in tile_coords_to_check:
            try:
                tile = lookaround.get_coverage_tile(tile_x, tile_y)
                if tile and tile.panos:
                    all_panos.extend(tile.panos)
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Could not fetch tile ({tile_x}, {tile_y}): {e}")
                continue
        
        if not all_panos:
            return {"success": False, "output": "No panoramas found in the selected coverage tiles.", "downloaded_files": []}
        
        if progress_callback:
            progress_callback(f"Found {len(all_panos)} total panorama(s) in search area")
        
        def distance(lat1, lon1, lat2, lon2):
            """Calculate simple Euclidean distance between two coordinates"""
            return math.sqrt(((lat1 - lat2) ** 2) + ((lon1 - lon2) ** 2))
        
        # Sort panoramas by distance and take the closest ones
        sorted_panos = sorted(all_panos, key=lambda p: distance(p.lat, p.lon, target_lat, target_lon))
        selected_panos = sorted_panos[:num_panos]
        
        if progress_callback:
            progress_callback(f"Selected {len(selected_panos)} closest panorama(s)")
            for i, pano in enumerate(selected_panos, 1):
                dist = distance(pano.lat, pano.lon, target_lat, target_lon)
                progress_callback(f"  {i}. Pano {pano.id} at {pano.lat}, {pano.lon} (distance: {dist:.8f}) - {pano.date}")
        
        # Process each selected panorama
        successful_downloads = 0
        failed_downloads = 0
        downloaded_files = []
        
        for pano_idx, pano in enumerate(selected_panos, 1):
            if progress_callback:
                progress_callback(f"Processing panorama {pano_idx}/{len(selected_panos)}: {pano.id}")
            
            faces = []
            face_download_success = True
            
            for face_idx in range(6):
                try:
                    face_heic = lookaround.get_panorama_face(pano, face_idx, zoom, auth)
                    face = ph.open_heif(face_heic, convert_hdr_to_8bit=False, bgr_mode=False)
                    np_arr = np.asarray(face)
                    faces.append(Image.fromarray(np_arr))
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Error downloading face {face_idx} for pano {pano.id}: {e}")
                    face_download_success = False
                    break
            
            if face_download_success and len(faces) == 6:
                try:
                    result = lookaround.to_equirectangular(faces, pano.camera_metadata)
                    output_filename = os.path.join(out_dir, f"{pano.id}_{zoom}.jpg")
                    result.save(output_filename, options={"quality": 100})
                    downloaded_files.append(output_filename)
                    if progress_callback:
                        progress_callback(f"Saved equirectangular panorama: {output_filename}")
                    successful_downloads += 1
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Error creating equirectangular panorama for pano {pano.id}: {e}")
                    failed_downloads += 1
            else:
                if progress_callback:
                    progress_callback(f"Could not download all 6 faces for pano {pano.id}. Skipping.")
                failed_downloads += 1
        
        # Summary
        output_lines = [
            f"=== Processing Complete ===",
            f"Successfully processed: {successful_downloads} panorama(s)",
            f"Failed to process: {failed_downloads} panorama(s)",
            f"Total requested: {num_panos}"
        ]
        
        if successful_downloads == 0:
            return {"success": False, "output": "\n".join(output_lines), "downloaded_files": []}
        elif failed_downloads > 0:
            output_lines.append(f"Warning: {failed_downloads} panorama(s) failed to process.")
        
        return {"success": True, "output": "\n".join(output_lines), "downloaded_files": downloaded_files}
        
    except Exception as e:
        return {"success": False, "output": f"Error in get_lookaround_panoramas: {str(e)}", "downloaded_files": []}

def convert_panorama_to_perspective(input_path, output_dir, fov=100, progress_callback=None):
    """
    Convert equirectangular panorama to perspective views
    
    Args:
        input_path: Path to input panorama
        output_dir: Output directory for perspective views
        fov: Field of view for perspective views
        progress_callback: Function to call with progress updates
    
    Returns:
        dict: {"success": bool, "output": str, "generated_files": list}
    """
    try:
        input_path = os.path.abspath(input_path)
        
        if not os.path.exists(input_path):
            return {"success": False, "output": f"File not found: {input_path}", "generated_files": []}
        
        file_name = os.path.basename(input_path).split('.')[0]
        perspective_dir = os.path.join(output_dir, "perspectives")
        os.makedirs(perspective_dir, exist_ok=True)
        
        if progress_callback:
            progress_callback(f"Loading image: {input_path}")
        
        # Load the image
        e_img = cv2.imread(input_path)[:, :, ::-1]
        
        if progress_callback:
            progress_callback(f"Loaded image shape: {e_img.shape}")
        
        # Generate perspective views
        num_pics = 8 
        yaw_vals = [i*(360//num_pics) for i in range(num_pics)]
        pitch_vals = [-30, 0, 30]
        
        tasks = [(pitch, yaw) for pitch in pitch_vals for yaw in yaw_vals]
        generated_files = []
        success_count = 0
        
        if progress_callback:
            progress_callback(f"Creating {len(tasks)} perspective views...")
        
        for i, (pitch, yaw) in enumerate(tasks):
            try:
                if progress_callback:
                    progress_callback(f"Creating perspective view {i+1}/{len(tasks)}: pitch={pitch}, yaw={yaw}")
                
                perspective_img = py360convert.e2p(
                    e_img,
                    fov_deg=(fov, fov),
                    u_deg=yaw,
                    v_deg=pitch,
                    out_hw=(1024, 1024),
                    in_rot_deg=0
                )
                
                out_file_name = os.path.join(perspective_dir, f"{file_name}_split_{yaw}_{pitch}.jpg")
                img = Image.fromarray(perspective_img)
                img.save(out_file_name)
                generated_files.append(out_file_name)
                success_count += 1
                
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Error processing pitch={pitch}, yaw={yaw}: {e}")
        
        output_summary = f"Perspective conversion complete! Successes: {success_count}, Expected: {len(tasks)}"
        
        return {
            "success": success_count > 0, 
            "output": output_summary, 
            "generated_files": generated_files
        }
        
    except Exception as e:
        return {"success": False, "output": f"Error in convert_panorama_to_perspective: {str(e)}", "generated_files": []}

def run_function_with_progress(func, title="Processing", **kwargs):
    """
    Run a function with real-time progress display
    
    Args:
        func: Function to run
        title: Display title
        **kwargs: Arguments to pass to function
    
    Returns:
        Function result
    """
    st.info(f" {title}...")
    output_placeholder = st.empty()
    progress_lines = []
    
    def progress_callback(message):
        progress_lines.append(str(message))
        recent_output = '\n'.join(progress_lines[-10:])
        output_placeholder.text_area(
            f" {title}:", 
            recent_output, 
            height=150,
            disabled=True
        )
    
    try:
        # Add progress callback to function arguments
        kwargs['progress_callback'] = progress_callback
        result = func(**kwargs)
        
        # Clear the output placeholder
        output_placeholder.empty()
        
        return result
        
    except Exception as e:
        output_placeholder.empty()
        st.error(f" Error: {str(e)}")
        return {"success": False, "output": str(e)}

def create_output_zip():
    """Creates a zip file of the current output directory"""
    if not (os.path.exists(st.session_state.output_dir)):
        return None
    
    all_files = []
    for root, dirs, files in os.walk(st.session_state.output_dir):
        for file in files:
            all_files.append(os.path.join(root, file))
    
    if not all_files:
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"panorama_session_{st.session_state.session_id}_{timestamp}.zip"
    zip_path = os.path.join(st.session_state.temp_dir, zip_filename)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in all_files:
            arcname = os.path.relpath(file_path, st.session_state.output_dir)
            zipf.write(file_path, arcname)
    
    return zip_path, zip_filename

def split_panoramas_to_perspective(file_list):
    """Split panoramas into perspective views"""
    
    total_files = len(file_list)
    st.info(f" Processing {total_files} panorama(s) into perspective views...")
    
    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    
    processed_successfully = 0
    all_outputs = []
    
    for i, (mod_time, filename, file_path) in enumerate(file_list):
        status_placeholder.info(f" Processing {filename} ({i+1}/{total_files})")
        
        result = run_function_with_progress(
            convert_panorama_to_perspective,
            title=f"Processing {filename}",
            input_path=file_path,
            output_dir=st.session_state.output_dir
        )
        
        if result["success"]:
            processed_successfully += 1
            status_placeholder.success(f"Completed {filename}")
            all_outputs.append(result["output"])
        else:
            status_placeholder.error(f"Failed to process {filename}")
            with st.expander(f"Error details for {filename}"):
                st.text(result["output"])
        
        progress_bar.progress((i + 1) / total_files)
    
    # Final status and show results
    if processed_successfully == total_files:
        st.success(f"Successfully processed all {total_files} panorama(s)!")
        show_perspective_results(file_list, st.session_state.output_dir)
    elif processed_successfully > 0:
        st.warning(f"️Processed {processed_successfully}/{total_files} panorama(s)")
        show_perspective_results(file_list, st.session_state.output_dir)
    else:
        st.error("Failed to process any panoramas")
    
    if all_outputs:
        with st.expander("Complete Processing Log"):
            st.text('\n'.join(all_outputs))

def show_perspective_results(recent_files, output_dir):
    """Display the generated perspective views"""
    
    st.markdown("---")
    st.subheader("️ Generated Perspective Views")
    
    base_output_dir = output_dir
    
    for mod_time, file, file_path in recent_files:
        file_name = os.path.splitext(file)[0]
        perspective_dir = os.path.join(base_output_dir, "perspectives")
        os.makedirs(perspective_dir, exist_ok=True)
        
        if os.path.exists(perspective_dir):
            perspective_files = [f for f in os.listdir(perspective_dir) if f.endswith('.jpg') and '_split_' in f]
            
            if perspective_files:
                st.write(f" **{file}** → {len(perspective_files)} perspective views")
                
                with st.expander(f"View perspectives from {file} ({len(perspective_files)} images)"):
                    perspective_files.sort()
                    
                    for i in range(0, min(9, len(perspective_files)), 3):
                        cols = st.columns(3)
                        for j, col in enumerate(cols):
                            if i + j < len(perspective_files):
                                perspective_file = perspective_files[i + j]
                                perspective_path = os.path.join(perspective_dir, perspective_file)
                                
                                try:
                                    parts = perspective_file.split('_split_')[1].replace('.jpg', '').split('_')
                                    yaw, pitch = parts[0], parts[1]
                                    caption = f"Yaw: {yaw}°, Pitch: {pitch}°"
                                except:
                                    caption = perspective_file
                                
                                col.image(perspective_path, caption=caption, use_container_width=True)
                    
                    if len(perspective_files) > 9:
                        st.info(f" Plus {len(perspective_files) - 9} more perspective views in {perspective_dir}")
            else:
                st.warning(f"️ No perspective views found for {file}")
        else:
            st.warning(f"️ Output directory not found for {file}")

st.set_page_config(
    page_title="Panorama Tools",
    layout="wide",
)

def initialize_session():
    """Initialize user session with proper isolation"""
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]
        
        base_temp = os.path.join(tempfile.gettempdir(), "panorama_app")
        os.makedirs(base_temp, exist_ok=True)
        
        st.session_state.temp_dir = os.path.join(base_temp, f"user_{st.session_state.session_id}")
        st.session_state.output_dir = os.path.join(st.session_state.temp_dir, "output")
        
        # Import script functions and set scripts directory
        st.session_state.scripts_dir = import_script_functions()
        if not st.session_state.scripts_dir:
            st.error("Failed to initialize script functions")
            st.stop()
        
        os.makedirs(st.session_state.output_dir, exist_ok=True)
        os.makedirs(os.path.join(st.session_state.temp_dir, "script_output"), exist_ok=True)
        
        cleanup_old_sessions(base_temp)
        st.session_state.cleanup_registered = True

def cleanup_old_sessions(base_temp, max_age_hours=24):
    """Clean up temp directories older than max_age_hours"""
    try:
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)
        
        for item in os.listdir(base_temp):
            item_path = os.path.join(base_temp, item)
            if os.path.isdir(item_path) and item.startswith("user_"):
                try:
                    dir_mtime = os.path.getmtime(item_path)
                    if dir_mtime < cutoff_time:
                        shutil.rmtree(item_path)
                except:
                    continue
    except:
        pass

def cleanup_session(session_temp_dir):
    """Clean up current session directory"""
    if session_temp_dir is None and 'temp_dir' in st.session_state:
        session_temp_dir = st.session_state.temp_dir
    
    if session_temp_dir and os.path.exists(session_temp_dir):
        try:
            shutil.rmtree(session_temp_dir)
        except:
            pass

initialize_session()

st.title("Panorama Tools")
st.markdown("Simple wrapper around some helpful scripts whose intent is to facilitate a painless workflow when it comes to producing gaussian splats.")

st.header("Get Panoramas")
st.write("Download panoramic images from street view services")

# Settings section
settings_col1, settings_col2= st.columns(2)
with settings_col1:
    num_panos = st.number_input("Number of Panoramas", min_value=1, max_value=500, value=3)
with settings_col2:
    zoom_level = st.selectbox("Zoom Level", options=[0, 1, 2, 3, 4, 5], index=2)
st.write("You can download a maximum of 500 panoramas at a time.")

st.markdown("---")

# Location selection section
st.subheader("Select Location")

if 'selected_lat' not in st.session_state:
    st.session_state.selected_lat = 42.3644583
if 'selected_lon' not in st.session_state:
    st.session_state.selected_lon = -71.0830152

curr_pos = [st.session_state.selected_lat, st.session_state.selected_lon]

m = folium.Map(
    location=curr_pos,
    zoom_start=15,
    tiles='CartoDB positron'
)

folium.Marker(
    curr_pos,
    popup=f"{curr_pos[0]:.4f}, {curr_pos[1]:.4f}",
    tooltip="Click map to change location",
    icon=folium.Icon(color='red', icon='info-sign')
).add_to(m)

folium.Circle(
    location=curr_pos,
    radius=100,
    fillColor='blue',
    fillOpacity=0.05,
    opacity=0.1,
).add_to(m)

map_data = st_folium(m, key="panorama_map", height=800, width=None)

if map_data['last_clicked'] is not None:
    st.session_state.selected_lat = map_data['last_clicked']['lat']
    st.session_state.selected_lon = map_data['last_clicked']['lng']
    st.rerun()

st.markdown("---")

# Download section
st.subheader(" Download Panoramas")

col1, col2, col3 = st.columns([1, 2, 1])
if 'recent_files' not in st.session_state:
    st.session_state.recent_files = None

with col2:
    if st.button(" Start Download", type="primary", use_container_width=True):
        
        result = run_function_with_progress(
            get_lookaround_panoramas,
            title=f"Downloading {num_panos} panoramas",
            target_lat=st.session_state.selected_lat,
            target_lon=st.session_state.selected_lon,
            out_dir=st.session_state.output_dir,
            num_panos=num_panos,
            zoom=zoom_level
        )
        
        if result["success"]:
            st.success(" Download completed successfully!") 
            
            if result["output"]:
                with st.expander(" View Download Summary"):
                    st.text(result["output"])
            
            # Display the newly downloaded images
            st.markdown("---")
            st.subheader("️ Downloaded Panoramas")
            
            downloaded_files = result["downloaded_files"]
            
            if downloaded_files:
                # Create recent_files format
                import time
                current_time = time.time()
                st.session_state.recent_files = []
                
                for file_path in downloaded_files:
                    file = os.path.basename(file_path)
                    mod_time = os.path.getmtime(file_path)
                    st.session_state.recent_files.append((mod_time, file, file_path))
                
                st.success(f" Successfully downloaded {len(st.session_state.recent_files)} new panoramas!")
                
                # Display images in a nice grid
                if len(st.session_state.recent_files) == 1:
                    mod_time, file, file_path = st.session_state.recent_files[0]
                    download_time = time.strftime('%H:%M:%S', time.localtime(mod_time))
                    st.image(file_path, caption=f" {file} (Downloaded: {download_time})", use_container_width=True)
                    
                elif len(st.session_state.recent_files) <= 3:
                    cols = st.columns(len(st.session_state.recent_files))
                    for i, (mod_time, file, file_path) in enumerate(st.session_state.recent_files):
                        download_time = time.strftime('%H:%M:%S', time.localtime(mod_time))
                        cols[i].image(file_path, caption=f" #{i+1}\n{download_time}", use_container_width=True)
                        
                else:
                    for i in range(0, len(st.session_state.recent_files), 3):
                        cols = st.columns(3)
                        for j, col in enumerate(cols):
                            if i + j < len(st.session_state.recent_files):
                                mod_time, file, file_path = st.session_state.recent_files[i + j]
                                download_time = time.strftime('%H:%M:%S', time.localtime(mod_time))
                                col.image(file_path, caption=f" #{i+j+1}\n{download_time}", use_container_width=True)
                
                # File details
                with st.expander(" File Details"):
                    for mod_time, file, file_path in st.session_state.recent_files:
                        file_size = os.path.getsize(file_path)
                        download_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mod_time))
                        st.write(f" **{file}** - {file_size:,} bytes - Downloaded: {download_time}")
                    
                    st.write(f" **Output Directory:** `{st.session_state.output_dir}`")
            else:
                st.warning(" No image files were downloaded")
                
        else:
            st.error(" Download failed!")
            st.text(result["output"])

st.markdown("---")
st.subheader(" Convert to Perspective Views")
st.write("Split panoramas into multiple perspective views for 3D reconstruction")

if st.session_state.recent_files:
    st.write(f" Ready to process {len(st.session_state.recent_files)} panorama(s)")
    for _, file, _ in st.session_state.recent_files:
        st.write(f"• {file}")
    
    if st.button(" Split to Perspectives", type="secondary", use_container_width=True):
        split_panoramas_to_perspective(st.session_state.recent_files)
else:
    st.write("**Or upload panoramas to split:**")
    uploaded_panos = st.file_uploader(
        "Upload panorama files", 
        type=["jpg", 'jpeg', 'png', 'bmp'], 
        accept_multiple_files=True,
        help="Upload equirectangular panorama images to split into perspective views"
    )
    
    if uploaded_panos:
        st.success(f" Uploaded {len(uploaded_panos)} panorama(s)")
        
        temp_dir = os.path.join(st.session_state.temp_dir, "uploads")
        os.makedirs(temp_dir, exist_ok=True)
        
        uploaded_file_paths = []
        for pano in uploaded_panos:
            temp_file_path = os.path.join(temp_dir, pano.name)
            with open(temp_file_path, "wb") as f:
                f.write(pano.getbuffer())
            uploaded_file_paths.append((None, pano.name, temp_file_path))
        
        preview_col1, preview_col2 = st.columns([3, 1])
        with preview_col1:
            st.write("**Uploaded files:**")
            for _, filename, _ in uploaded_file_paths:
                st.write(f"• {filename}")
        
        with preview_col2:
            if st.button(" Split Uploaded Panoramas", type="secondary", use_container_width=True):
                split_panoramas_to_perspective(uploaded_file_paths)

if (st.session_state.recent_files or 
    (os.path.exists(st.session_state.output_dir) and 
     os.listdir(st.session_state.output_dir))):
    
    st.markdown("---")
    st.subheader(" Download Results")
    
    total_files = 0
    if os.path.exists(st.session_state.output_dir):
        for root, dirs, files in os.walk(st.session_state.output_dir):
            total_files += len(files)
    
    if total_files > 0:
        st.write(f" Your session contains {total_files} files ready for download")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.write("Download all generated panoramas and perspective views as a ZIP file")
        
        with col2:
            if st.button(" Create & Download ZIP", type="primary", use_container_width=True):
                with st.spinner("Creating ZIP file..."):
                    zip_result = create_output_zip()
                    
                    if zip_result:
                        zip_path, zip_filename = zip_result
                        
                        with open(zip_path, "rb") as f:
                            zip_data = f.read()
                        
                        st.download_button(
                            label="️ Download ZIP",
                            data=zip_data,
                            file_name=zip_filename,
                            mime="application/zip",
                            use_container_width=True
                        )
                        
                        zip_size = len(zip_data)
                        st.success(f" ZIP created: {zip_filename} ({zip_size:,} bytes)")
                        
                    else:
                        st.error(" No files found to zip")
    else:
        st.info(" No files generated yet. Download panoramas or create perspectives first.")

if st.session_state.get("cleanup_registered", False):
    with st.sidebar:
        st.markdown('---')
        st.subheader('Session Management')
        if st.button('Clear Session Files', help="Delete all files from the session"):
            cleanup_session(st.session_state.temp_dir)
            st.success("Session files cleared!")
            st.rerun()