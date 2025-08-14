import streamlit as st
import os
import subprocess
import sys
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile
import uuid
import atexit
import shutil

try:
    import folium
    from streamlit_folium import st_folium
except ImportError:
    pass

def split_panoramas_to_perspective(file_list, scripts_dir):
    """Split panoramas into perspective views using to_perspective.py"""
    
    script_name = "to_perspective.py"
    script_path = os.path.join(scripts_dir, script_name)
    
    if not os.path.exists(script_path):
        st.error("❌ to_perspective.py script not found!")
        st.write(f"Expected location: {script_path}")
        return
    
    total_files = len(file_list)
    st.info(f"🔄 Processing {total_files} panorama(s) into perspective views...")
    
    # Create progress tracking
    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    output_placeholder = st.empty()
    
    processed_successfully = 0
    all_outputs = []
    
    for i, (mod_time, filename, file_path) in enumerate(file_list):
        status_placeholder.info(f"🎯 Processing {filename} ({i+1}/{total_files})")
        
        try:
            # Your to_perspective.py script expects just the file path
            cmd = [sys.executable, script_path, file_path, st.session_state.output_dir]
            
            # Run with real-time output capture
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Collect output lines
            output_lines = []
            for line in iter(process.stdout.readline, ''):
                if line.strip():
                    output_lines.append(line.strip())
                    
                    # Show recent output (last 3 lines)
                    recent_output = '\n'.join(output_lines[-3:])
                    output_placeholder.text_area(
                        f"Processing {filename}:", 
                        recent_output, 
                        height=80,
                        disabled=True
                    )
            
            process.wait()
            
            if process.returncode == 0:
                processed_successfully += 1
                status_placeholder.success(f"Completed {filename}")
                all_outputs.extend(output_lines)
            else:
                status_placeholder.error(f"Failed to process {filename}")
                with st.expander(f"Error details for {filename}"):
                    st.text('\n'.join(output_lines))
        
        except subprocess.TimeoutExpired:
            st.error(f"⏰ Processing {filename} timed out")
        except Exception as e:
            st.error(f"💥 Error processing {filename}: {str(e)}")
        
        # Update progress
        progress_bar.progress((i + 1) / total_files)
    
    # Clear the output placeholder
    output_placeholder.empty()
    
    # Final status and show results
    if processed_successfully == total_files:
        st.success(f"🎉 Successfully processed all {total_files} panorama(s)!")
        st.balloons()
        show_perspective_results(file_list, st.session_state.output_dir)
    elif processed_successfully > 0:
        st.warning(f"⚠️ Processed {processed_successfully}/{total_files} panorama(s)")
        show_perspective_results(file_list, st.session_state.output_dir)
    else:
        st.error("❌ Failed to process any panoramas")
    
    # Show complete processing log
    if all_outputs:
        with st.expander("📄 Complete Processing Log"):
            st.text('\n'.join(all_outputs))

def run_script_realtime(cmd, title="Running Script", timeout=120, success_keywords=None, output_dir=None):
    """
    Run a script with real-time output display in Streamlit
    
    Args:
        cmd: List of command arguments (e.g., [sys.executable, script_path, arg1, arg2])
        title: Display title for the progress area
        timeout: Timeout in seconds
        success_keywords: List of strings to check for success (default: ["Successfully", "100%", "completed"])
    
    Returns:
        dict: {"success": bool, "output": str, "returncode": int}
    """
    if output_dir is None:
        output_dir=st.session_state.output_dir

    if success_keywords is None:
        success_keywords = ["Successfully", "100%", "completed", "SUCCESS"]
    
    st.info(f"🔄 {title}...")
    output_placeholder = st.empty()
    progress_lines = []
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Read output line by line in real-time
        for line in iter(process.stdout.readline, ''):
            if line.strip():
                progress_lines.append(line.strip())
                
                # Show last 10 lines in real-time
                recent_output = '\n'.join(progress_lines[-10:])
                output_placeholder.text_area(
                    f"📡 {title}:", 
                    recent_output, 
                    height=150,
                    disabled=True
                )
        
        process.wait()
        
        # Clear the output placeholder
        output_placeholder.empty()
        
        # Check for success
        full_output = '\n'.join(progress_lines)
        has_success_keywords = any(keyword in full_output for keyword in success_keywords)
        success = process.returncode == 0 or has_success_keywords
        
        return {
            "success": success,
            "output": full_output,
            "returncode": process.returncode
        }
        
    except subprocess.TimeoutExpired:
        st.error(f"⏰ {title} timed out after {timeout} seconds")
        return {"success": False, "output": "", "returncode": -1}
    except Exception as e:
        st.error(f"💥 Error running script: {str(e)}")
        return {"success": False, "output": str(e), "returncode": -1}

def show_perspective_results(recent_files, output_dir):
    """Display the generated perspective views"""
    
    st.markdown("---")
    st.subheader("🖼️ Generated Perspective Views")
    
    base_output_dir = output_dir
    
    for mod_time, file, file_path in recent_files:
        file_name = os.path.splitext(file)[0]
        perspective_dir = os.path.join(base_output_dir, "perspectives")
        os.makedirs(perspective_dir, exist_ok=True)
        
        if os.path.exists(perspective_dir):
            perspective_files = [f for f in os.listdir(perspective_dir) if f.endswith('.jpg') and '_split_' in f]
            
            if perspective_files:
                st.write(f"📸 **{file}** → {len(perspective_files)} perspective views")
                
                # Show first few perspective views in a grid
                with st.expander(f"View perspectives from {file} ({len(perspective_files)} images)"):
                    # Sort perspective files by name for consistent ordering
                    perspective_files.sort()
                    
                    # Show in grid of 3 columns
                    for i in range(0, min(9, len(perspective_files)), 3):  # Show max 9 images
                        cols = st.columns(3)
                        for j, col in enumerate(cols):
                            if i + j < len(perspective_files):
                                perspective_file = perspective_files[i + j]
                                perspective_path = os.path.join(perspective_dir, perspective_file)
                                
                                # Extract angle info from filename for caption
                                try:
                                    parts = perspective_file.split('_split_')[1].replace('.jpg', '').split('_')
                                    yaw, pitch = parts[0], parts[1]
                                    caption = f"Yaw: {yaw}°, Pitch: {pitch}°"
                                except:
                                    caption = perspective_file
                                
                                col.image(perspective_path, caption=caption, use_container_width=True)
                    
                    if len(perspective_files) > 9:
                        st.info(f"📁 Plus {len(perspective_files) - 9} more perspective views in {perspective_dir}")
            else:
                st.warning(f"⚠️ No perspective views found for {file}")
        else:
            st.warning(f"⚠️ Output directory not found for {file}")

def run_simple_test(script_name):
    upper_dir = os.path.dirname(os.getcwd())
    script_path = os.path.join(st.session_state.scripts_dir, script_name)

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return True, f"Script found: {script_name}", result

    except Exception as e:
        print(f"Script didn't work: {e}")

st.set_page_config(
        page_title="Panorama Tools",
        layout="wide",
        )

def initialize_session():
    """Initialize user session with unique temp directory"""
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.temp_dir = tempfile.mkdtemp(prefix=f"panorama_{st.session_state.session_id}_")
        st.session_state.output_dir = os.path.join(st.session_state.temp_dir, "output")
        st.session_state.scripts_dir = os.path.join(os.path.dirname(os.getcwd()), "scripts")
        os.makedirs(st.session_state.output_dir, exist_ok=True)
        
        # Register cleanup on exit
        atexit.register(cleanup_session, st.session_state.temp_dir)

def cleanup_session(temp_dir):
    """Clean up temporary directory"""
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    except:
        pass

initialize_session()

st.title("Panorama Tools")
st.markdown("Simple wrapper around some helpful scripts whose intent is to facilitate a painless workflow when it comes to producing gaussian splats.")

st.header("Get Panoramas")
st.write("Download panoramic images from street view services")

# Settings section at the top

settings_col1, settings_col2, settings_col3 = st.columns(3)
with settings_col1:
    num_panos = st.number_input("Number of Panoramas", min_value=1, max_value=500, value=3)
with settings_col2:
    zoom_level = st.selectbox("Zoom Level", options=[0, 1, 2, 3, 4, 5], index=2)
with settings_col3:
    service = st.selectbox("Service", ["Google Street View", "Apple Look Around"])
st.write("You can download a maximum of 500 panoramas at a time.")
st.write("For Apple: the lower the zoom level, the higher the quality.")
st.write("For Google: the lower the zoom level, the lower the quality.")

st.markdown("---")

# Location selection section
st.subheader("Select Location")

# Initialize session state
if 'selected_lat' not in st.session_state:
    st.session_state.selected_lat = 42.3644583
if 'selected_lon' not in st.session_state:
    st.session_state.selected_lon = -71.0830152

# Full-width map
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
    radius=100,  # Increased radius for better visibility
    fillColor='blue',
    fillOpacity=0.05,
    opacity=0.1,
).add_to(m)

# Full-width map
map_data = st_folium(m, key="panorama_map", height=800, width=None)

# Update coordinates when map is clicked
if map_data['last_clicked'] is not None:
    st.session_state.selected_lat = map_data['last_clicked']['lat']
    st.session_state.selected_lon = map_data['last_clicked']['lng']
    st.rerun()

st.markdown("---")

# Download section
st.subheader("🚀 Download Panoramas")

# Summary before download
st.info(f"📋 Ready to download {num_panos} panoramas from {service} at zoom level {zoom_level}")

# Centered download button
col1, col2, col3 = st.columns([1, 2, 1])
if 'recent_files' not in st.session_state:
    st.session_state.recent_files = None

with col2:
    if st.button("📥 Start Download", type="primary", use_container_width=True):
        with st.spinner(f"Downloading {num_panos} panoramas from {service}..."):
            # Determine script
            script_name = "get_lookaround.py" if "Apple" in service else "get_streetview.py"
            
            script_path = os.path.join(st.session_state.scripts_dir, script_name)
            
            cmd = [
                sys.executable,
                script_path,
                str(st.session_state.selected_lat),
                str(st.session_state.selected_lon),
                str(num_panos),
                str(zoom_level),
            ]
            
            st.info(f"🔄 Running: {' '.join([os.path.basename(p) for p in cmd])}")

            try:
                result = run_script_realtime(
                    cmd=cmd,
                    title=f"Downloading {num_panos}...",
                    timeout=240,
                    success_keywords=["panorama(s)"].extend("Successfully processed".split())
                )

                if result["success"]:
                    script_output_dir = os.path.join(os.path.dirname(os.getcwd()), "data", "output")
                    if os.path.exists(script_output_dir):
                        import time
                        current_time = time.time()
                        for file in os.listdir(script_output_dir):
                            if file.endswith(('.jpg', '.jpeg', '.png')):
                                src_path = os.path.join(script_output_dir, file)
                                # Only copy recent files (within last 2 minutes)
                                if current_time - os.path.getmtime(src_path) < 120:
                                    dst_path = os.path.join(st.session_state.output_dir, file)
                                    shutil.copy2(src_path, dst_path)
    
                    st.success("✅ Download completed successfully!") 
                    # Show script output
                    if result["output"]:
                        with st.expander("📋 View Script Output"):
                            st.text(result["output"])
                    
                    # Display the newly downloaded images
                    st.markdown("---")
                    st.subheader("🖼️ Downloaded Panoramas")
                    
                    out_dir = st.session_state.output_dir
                    
                    if os.path.exists(out_dir):
                        # Get all image files
                        all_files = [f for f in os.listdir(out_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
                        
                        if all_files:
                            # Sort files by modification time (newest first)
                            import time
                            files_with_time = []
                            current_time = time.time()
                            
                            for file in all_files:
                                file_path = os.path.join(out_dir, file)
                                mod_time = os.path.getmtime(file_path)
                                files_with_time.append((mod_time, file, file_path))
                            
                            # Sort by modification time (newest first)
                            files_with_time.sort(reverse=True)
                            
                            # Show only recently created files (within last 2 minutes)
                            st.session_state.recent_files = [
                                (mod_time, file, file_path) 
                                for mod_time, file, file_path in files_with_time 
                                if current_time - mod_time < 120
                            ]
                            if st.session_state.recent_files:
                                st.success(f"🎉 Successfully downloaded {len(st.session_state.recent_files)} new panoramas!")
                                
                                # Display images in a nice grid
                                if len(st.session_state.recent_files) == 1:
                                    # Single image - show large
                                    mod_time, file, file_path = st.session_state.recent_files[0]
                                    download_time = time.strftime('%H:%M:%S', time.localtime(mod_time))
                                    st.image(file_path, caption=f"📸 {file} (Downloaded: {download_time})", use_container_width=True)
                                    
                                elif len(st.session_state.recent_files) <= 3:
                                    # Few images - show in columns
                                    cols = st.columns(len(st.session_state.recent_files))
                                    for i, (mod_time, file, file_path) in enumerate(st.session_state.recent_files):
                                        download_time = time.strftime('%H:%M:%S', time.localtime(mod_time))
                                        cols[i].image(file_path, caption=f"📸 #{i+1}\n{download_time}", use_container_width=True)
                                        
                                else:
                                    # Many images - show in grid of 3 columns
                                    for i in range(0, len(st.session_state.recent_files), 3):
                                        cols = st.columns(3)
                                        for j, col in enumerate(cols):
                                            if i + j < len(st.session_state.recent_files):
                                                mod_time, file, file_path = st.session_state.recent_files[i + j]
                                                download_time = time.strftime('%H:%M:%S', time.localtime(mod_time))
                                                col.image(file_path, caption=f"📸 #{i+j+1}\n{download_time}", use_container_width=True)
                                
                                # File details
                                with st.expander("📁 File Details"):
                                    for mod_time, file, file_path in st.session_state.recent_files:
                                        file_size = os.path.getsize(file_path)
                                        download_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mod_time))
                                        st.write(f"📄 **{file}** - {file_size:,} bytes - Downloaded: {download_time}")
                                    
                                    # Show output directory
                                    st.write(f"📂 **Output Directory:** `{out_dir}`")
                            
                            else:
                                st.warning("⚠️ No recently downloaded files found. Showing most recent files:")
                                # Show the 3 most recent files anyway
                                for i, (mod_time, file, file_path) in enumerate(files_with_time[:3]):
                                    download_time = time.strftime('%H:%M:%S', time.localtime(mod_time))
                                    st.image(file_path, caption=f"📸 {file} (Modified: {download_time})", width=400)
                        else:
                            st.warning("📁 No image files found in output directory")
                    else:
                        st.warning("📁 Output directory not found")
                        
                else:
                    st.error("❌ Download failed!")
                    st.text(result["output"])
                    #if result.stderr:
                    #    with st.expander("🔍 Error Details"):
                    #        st.text(result.stderr)

            except subprocess.TimeoutExpired:
                st.error("⏰ Download timed out (took longer than 2 minutes)")
            except Exception as e:
                st.error(f"💥 Unexpected error: {str(e)}")
st.markdown("---")
st.subheader("🔄 Convert to Perspective Views")
st.write("Split panoramas into multiple perspective views for 3D reconstruction")

if st.session_state.recent_files:
    st.write(f"📋 Ready to process {len(st.session_state.recent_files)} panorama(s)")
    for _, file, _ in st.session_state.recent_files:  # Fixed: was *, file, * 
        st.write(f"• {file}")
    
    if st.button("🎯 Split to Perspectives", type="secondary", use_container_width=True):
        st.write("DEBUG: Split button clicked!")
        st.write(f"DEBUG: st.session_state.recent_files = {len(st.session_state.recent_files) if st.session_state.recent_files else 'None'}")
        st.write(f"DEBUG: upper_dir = {st.session_state.scripts_dir}")
        split_panoramas_to_perspective(st.session_state.recent_files, st.session_state.scripts_dir)
else:
    st.write("**Or upload panoramas to split:**")
    uploaded_panos = st.file_uploader(
        "Upload panorama files", 
        type=["jpg", 'jpeg', 'png', 'bmp'], 
        accept_multiple_files=True,
        help="Upload equirectangular panorama images to split into perspective views"
    )
    
    if uploaded_panos:
        st.success(f"✅ Uploaded {len(uploaded_panos)} panorama(s)")
        
        # Save uploaded files temporarily and process them
        temp_dir = os.path.join(st.session_state.temp_dir, "uploads")
        os.makedirs(temp_dir, exist_ok=True)
        
        uploaded_file_paths = []
        for pano in uploaded_panos:
            # Save uploaded file
            temp_file_path = os.path.join(temp_dir, pano.name)
            with open(temp_file_path, "wb") as f:
                f.write(pano.getbuffer())
            uploaded_file_paths.append((None, pano.name, temp_file_path))  # Match recent_files format
        
        # Show upload preview
        preview_col1, preview_col2 = st.columns([3, 1])
        with preview_col1:
            st.write("**Uploaded files:**")
            for _, filename, _ in uploaded_file_paths:
                st.write(f"• {filename}")
        
        with preview_col2:
            if st.button("🎯 Split Uploaded Panoramas", type="secondary", use_container_width=True):
                split_panoramas_to_perspective(st.session_state.recent_files, st.session_state.scripts_dir)