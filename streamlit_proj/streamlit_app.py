import streamlit as st
import os
import subprocess
import sys
import numpy as np
import pandas as pd
from PIL import Image
from pathlib import Path

try:
    import folium
    from streamlit_folium import st_folium
except ImportError:
    pass

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
    st.header("Get Panoramas")
    st.write("Download panoramic images from street view services")
    st.info("This section is a work in progress!")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Select Location")
        # Initialize session state for coordinates if not exists
        if 'selected_lat' not in st.session_state:
            st.session_state.selected_lat = 42.3644583  # Default to your example
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
                popup=f"{curr_pos[0]}, {curr_pos[1]}",
                tooltip="Click map to change location",
                icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)

        folium.Circle(
            location=curr_pos,
            radius=50,
            tooltip="Search Area",
            fillColor='Blue',
            fillOpacity=0.2,
            opacity=0.8,
        ).add_to(m)
        
        # Display the map and capture click events
        map_data = st_folium(m, key="panorama_map", height=600, width=800)
        
        # Update coordinates when map is clicked
        if map_data['last_clicked'] is not None:
            st.session_state.selected_lat = map_data['last_clicked']['lat']
            st.session_state.selected_lon = map_data['last_clicked']['lng']
            st.rerun()  # Refresh to update the marker
    
    with col2:
        st.subheader("Settings")
        
        # Display current coordinates
        st.write("**Selected Coordinates:**")
        st.write(f"Latitude: {st.session_state.selected_lat:.6f}")
        st.write(f"Longitude: {st.session_state.selected_lon:.6f}")
        
        st.markdown("---")
        
        # Panorama settings
        num_panos = st.number_input("Number of Panoramas", min_value=1, max_value=500, value=3)
        zoom_level = st.selectbox("Zoom Level", options=[0, 1, 2, 3, 4, 5], index=2)
        
        # Service selection
        service = st.selectbox("Service", ["Google Street View", "Apple Look Around"])
        
        st.markdown("---")
        
        # Download button
        if st.button("🚀 Download Panoramas", type="primary"):
            with st.spinner("Downloading panoramas..."):
                # Here we'll call your actual scripts
                st.success(f"Started download for {num_panos} panoramas at {st.session_state.selected_lat:.6f}, {st.session_state.selected_lon:.6f}")
                # TODO: Integrate actual script calls here
# Footer
st.markdown("---")
st.markdown("*Built with Streamlit*")
