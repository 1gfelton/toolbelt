from concurrent.futures import ThreadPoolExecutor as tpe
import py360convert
import numpy as np
import cv2
import os
import sys
from PIL import Image

def generate_and_save(e_img, file_name, out_dir, fov, pitch, yaw):
    print(f"Creating pano with pitch {pitch} and yaw {yaw}")
    perspective_img = py360convert.e2p(
        e_img,
        fov_deg=(fov, fov),
        u_deg=yaw,
        v_deg=pitch,
        out_hw=(1024, 1024),  # Reduced size for safety
        in_rot_deg=0
    )

    out_file_name = os.path.join(out_dir, f"{file_name}_split_{yaw}_{pitch}.jpg") 
    print(f"Saving file: {out_file_name}")
    
    img = Image.fromarray(perspective_img)
    img.save(out_file_name)

def pano_to_perspective(input_path, output_dir=None, fov=100, yaw=0, pitch=0):
    input_path = os.path.abspath(input_path)
    print(f"Input path: {input_path}")
    
    if not os.path.exists(input_path):
        print(f"ERROR: File not found: {input_path}")
        return False
    
    file_name = os.path.basename(input_path).split('.')[0]
    print(f"File name: {file_name}")

    if len(sys.argv) > 2:
        base_output_dir = sys.argv[2]
        out_dir = os.path.join(base_output_dir, "perspectives")
    else:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "output", "perspectives")

    print(f"Output directory: {out_dir}")
    os.makedirs(out_dir, exist_ok=True)
    
    # Load the image
    try:
        e_img = cv2.imread(input_path)[:, :, ::-1]
        print(f"Loaded image shape: {e_img.shape}")
    except Exception as e:
        print(f"ERROR loading image: {e}")
        return False
    num_pics = 8 
    success_count = 0
    # Safer: fewer perspectives, processed sequentially
    yaw_vals = [i*(360//num_pics) for i in range(num_pics)]  # 4 cardinal directions
    pitch_vals = [-30, 0, 30]
    expected = len(pitch_vals) * len(yaw_vals)
    tasks = [(pitch, yaw) for pitch in pitch_vals for yaw in yaw_vals]
    
    print(f"Creating {len(tasks)} perspective views...")
    
    # Process sequentially to avoid memory issues
    for pitch, yaw in tasks:
        try:
            generate_and_save(e_img, file_name, out_dir, fov, pitch, yaw)
            success_count+=1 
        except Exception as e:
            print(f"ERROR processing pitch={pitch}, yaw={yaw}: {e}")
            
    print("Perspective conversion complete!")
    print(f"Successes: {success_count}, Expected: {expected}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python to_perspective_fixed.py <image_path> <output_path>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_dir = sys.argv[2] 
    success = pano_to_perspective(input_path, output_dir)
    
    if not success:
        sys.exit(1)