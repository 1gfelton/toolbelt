import streamlit as st
import os
import subprocess
import sys
import numpy as np
import pandas as pd
from pathlib import Path

try:
    import folium
    from streamlit_folium import st_folium
except ImportError:
    pass

def split_panoramas_to_perspective(file_list, upper_dir):
    """Split panoramas into perspective views using to_perspective.py"""
    
    script_name = "to_perspective.py"
    script_path = os.path.join(upper_dir, "scripts", script_name)
    
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
            cmd = [sys.executable, script_path, file_path]
            
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
        show_perspective_results(file_list, upper_dir)
    elif processed_successfully > 0:
        st.warning(f"⚠️ Processed {processed_successfully}/{total_files} panorama(s)")
        show_perspective_results(file_list, upper_dir)
    else:
        st.error("❌ Failed to process any panoramas")
    
    # Show complete processing log
    if all_outputs:
        with st.expander("📄 Complete Processing Log"):
            st.text('\n'.join(all_outputs))

def run_script_realtime(cmd, title="Running Script", timeout=120, success_keywords=None):
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

def show_perspective_results(recent_files, upper_dir):
    """Display the generated perspective views"""
    
    st.markdown("---")
    st.subheader("🖼️ Generated Perspective Views")
    
    base_output_dir = os.path.join(upper_dir, "data", "output")
    
    for mod_time, file, file_path in recent_files:
        file_name = os.path.splitext(file)[0]
        perspective_dir = os.path.join(base_output_dir, "perspectives")
        
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
    script_path = os.path.join(upper_dir, "scripts", script_name)

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

st.title("Panorama Tools")
st.markdown("Simple wrapper around some helpful scripts whose intent is to facilitate a painless workflow when it comes to producing gaussian splats.")

st.sidebar.title("Tools")
tool_choice = st.sidebar.selectbox(
        "Choose a tool:",
        ["Home", "Get Panoramas",],
        )

if tool_choice == "Home":
    st.header("Welcome")
    st.write("This app is a GUI")

    if st.button("Test setup"):
        result = run_simple_test("get_lookaround.py")
        st.write(result)

        if os.path.exists("scripts"):
            st.subheader("Available Scripts:")
            scripts = [f for f in os.listdir(os.path.join(os.path.dirname(os.path.getcwd()), "scripts"))]
            for s in scripts:
                st.write(f"- {s}")

elif tool_choice == "Get Panoramas":
    st.header("🌍 Get Panoramas")
    st.write("Download panoramic images from street view services")
    
    # Settings section at the top
    st.subheader("⚙️ Settings")
    st.write("You can download a maximum of 500 panoramas at a time. For Google Streetview, the higher the zoom value, the higher the quality. For Apple Lookaround, the lower the zoom value, the higher the quality.")
    
    settings_col1, settings_col2, settings_col3 = st.columns(3)
    with settings_col1:
        num_panos = st.number_input("Number of Panoramas", min_value=1, max_value=500, value=3)
    with settings_col2:
        zoom_level = st.selectbox("Zoom Level", options=[0, 1, 2, 3, 4, 5], index=2)
    with settings_col3:
        service = st.selectbox("Service", ["Google Street View", "Apple Look Around"])
    
    st.markdown("---")
    
    # Location selection section
    st.subheader("📍 Select Location")
    
    # Initialize session state
    if 'selected_lat' not in st.session_state:
        st.session_state.selected_lat = 42.3644583
    if 'selected_lon' not in st.session_state:
        st.session_state.selected_lon = -71.0830152

    # Show current coordinates prominently
    coord_col1, coord_col2 = st.columns(2)
    with coord_col1:
        st.metric("📍 Latitude", f"{st.session_state.selected_lat:.6f}")
    with coord_col2:
        st.metric("📍 Longitude", f"{st.session_state.selected_lon:.6f}")

    # Full-width map
    curr_pos = [st.session_state.selected_lat, st.session_state.selected_lon]
    
    m = folium.Map(
        location=curr_pos,
        zoom_start=15,
        tiles='CartoDB positron'
    )

    folium.Marker(
        curr_pos,
        popup=f"📍 {curr_pos[0]:.4f}, {curr_pos[1]:.4f}",
        tooltip="Click map to change location",
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)

    folium.Circle(
        location=curr_pos,
        radius=100,  # Increased radius for better visibility
        tooltip=f"Search Area - {service}",
        fillColor='blue',
        fillOpacity=0.15,
        opacity=0.6,
    ).add_to(m)
    
    # Full-width map
    map_data = st_folium(m, key="panorama_map", height=400, width=None)
    
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

    upper_dir = os.path.dirname(os.getcwd())
    with col2:
        if st.button("📥 Start Download", type="primary", use_container_width=True):
            with st.spinner(f"Downloading {num_panos} panoramas from {service}..."):
                # Determine script
                script_name = "get_lookaround.py" if "Apple" in service else "get_streetview.py"
                
                script_path = os.path.join(upper_dir, "scripts", script_name)
                
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
                        st.success("✅ Download completed successfully!") 
                        # Show script output
                        if result["output"]:
                            with st.expander("📋 View Script Output"):
                                st.text(result["output"])
                        
                        # Display the newly downloaded images
                        st.markdown("---")
                        st.subheader("🖼️ Downloaded Panoramas")
                        
                        out_dir = os.path.join(upper_dir, "data", "output")
                        
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
            st.write(f"DEBUG: upper_dir = {upper_dir}")
            split_panoramas_to_perspective(st.session_state.recent_files, upper_dir) 
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
            temp_dir = os.path.join(upper_dir, "temp")
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
                    split_panoramas_to_perspective(uploaded_file_paths, upper_dir)

    # Add this function before your main app code (after imports):

    def show_perspective_results(file_list, upper_dir):
        """Display the generated perspective views"""
        
        st.markdown("---")
        st.subheader("🖼️ Generated Perspective Views")
        
        base_output_dir = os.path.join(upper_dir, "data", "output")
        total_perspectives = 0
        
        for mod_time, filename, file_path in file_list:
            # Get the filename without extension for the output directory
            file_name = os.path.splitext(filename)[0]
            perspective_dir = os.path.join(base_output_dir, "perspectives")
            st.write(f"🔍 **Debug Info:**")
            st.write(f"- Looking for: `{perspective_dir}`")
            st.write(f"- Directory exists: {os.path.exists(perspective_dir)}")
            st.write(f"- Base output dir exists: {os.path.exists(base_output_dir)}")

            if os.path.exists(base_output_dir):
                contents = os.listdir(base_output_dir)
                st.write(f"- Contents of output dir: {contents}")
            
            if os.path.exists(perspective_dir):
                # Look for perspective files (based on your to_perspective.py output pattern)
                perspective_files = [f for f in os.listdir(perspective_dir) if f.endswith('.jpg') and '_split_' in f]
                
                if perspective_files:
                    total_perspectives += len(perspective_files)
                    
                    with st.expander(f"📸 {filename} → {len(perspective_files)} perspective views", expanded=True):
                        # Sort files for organized display
                        perspective_files.sort()
                        
                        # Parse and group by pitch and yaw for better organization
                        grouped_views = {}
                        for pf in perspective_files:
                            try:
                                # Extract yaw and pitch from filename pattern: {name}_split_{yaw}_{pitch}.jpg
                                parts = pf.split('_split_')[1].replace('.jpg', '').split('_')
                                yaw, pitch = int(parts[0]), int(parts[1])
                                
                                if pitch not in grouped_views:
                                    grouped_views[pitch] = []
                                grouped_views[pitch].append((yaw, pf))
                            except (IndexError, ValueError):
                                # Handle files that don't match expected pattern
                                if 'other' not in grouped_views:
                                    grouped_views['other'] = []
                                grouped_views['other'].append((0, pf))
                        
                        # Display each pitch level
                        for pitch in sorted(grouped_views.keys()):
                            if pitch != 'other':
                                st.write(f"**Pitch: {pitch}°**")
                            else:
                                st.write("**Other views:**")
                            
                            # Sort by yaw and display in rows of 3
                            yaw_files = sorted(grouped_views[pitch]) if pitch != 'other' else grouped_views[pitch]
                            
                            for row_start in range(0, len(yaw_files), 3):
                                cols = st.columns(3)
                                for col_idx, col in enumerate(cols):
                                    file_idx = row_start + col_idx
                                    if file_idx < len(yaw_files):
                                        yaw, pf = yaw_files[file_idx]
                                        perspective_path = os.path.join(perspective_dir, pf)
                                        
                                        if pitch != 'other':
                                            caption = f"Yaw: {yaw}°"
                                        else:
                                            caption = pf
                                        
                                        col.image(perspective_path, caption=caption, use_container_width=True)
                        
                        # Show directory info
                        st.info(f"📁 {len(perspective_files)} perspective views saved to: `{perspective_dir}`")
                else:
                    st.warning(f"⚠️ No perspective views found for {filename}")
                    st.write("Expected files with pattern: `{filename}_split_{yaw}_{pitch}.jpg`")
            else:
                st.warning(f"⚠️ Output directory not found for {filename}")
                st.write(f"Expected directory: `{perspective_dir}`")
        
        if total_perspectives > 0:
            st.success(f"🎯 **Total: {total_perspectives} perspective views generated!**")
            st.info("💡 **Next steps:** These perspective views are ready for photogrammetry software like COLMAP, Reality Capture, or gaussian splatting pipelines!")
            
            # Show output directory for easy access
            st.write(f"📂 **All outputs saved to:** `{base_output_dir}`")
            
            if st.button("📁 Open Output Directory"):
                import webbrowser
                webbrowser.open(os.path.abspath(base_output_dir))