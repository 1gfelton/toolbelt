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
        out_hw=(2048, 2048),
        in_rot_deg=0
    )

    out_file_name = os.path.join(out_dir, f"{file_name}_split_{yaw}_{pitch}.jpg") 
    print(f"Saving file: {out_file_name}")
    # Save the result
    if isinstance(perspective_img, str):
        # If e2p returns path, copy to desired location
        img = Image.open(perspective_img)
        img.save(out_file_name)
    else:
        # If e2p returns image array
        img = Image.fromarray(perspective_img)
        img.save(out_file_name)

def pano_to_perspective(input_path, output_path, fov=90, yaw=0, pitch=0):
    base_name = os.path.basename(os.path.dirname(input_path))
    print(f"Base name: {base_name}")
    file_name = os.path.basename(input_path).split('.')[0]
    print(f"File name: {file_name}")

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "output", file_name)
    print(f"Out dir: {out_dir}")
    os.makedirs(out_dir, exist_ok=True)
    # load the image
    e_img = cv2.imread(input_path)[:, :, ::-1]
    pitch_vals = [0, 15, 30] # base yaw, slightly tilted up, and looking all the way up
    total_imgs = 18
    num_imgs_per_ring = total_imgs//3
    yaw = 360//num_imgs_per_ring
    # 360 / 3 = 120 -> 0, 120, 240 -> 0 + yaw * i -> 0 + 0 * 0, (0 + 120 * 1), (0 + 120 * 2)
    yaw_vals = [yaw*i for i in range(num_imgs_per_ring)]

    tasks = [(pitch, yaw) for pitch in pitch_vals for yaw in yaw_vals]
    with tpe() as executor:
        executor.map(lambda args: generate_and_save(e_img, file_name, out_dir, fov, args[0], args[1]), tasks)

if __name__ == "__main__":
    file_name = os.path.join("c:", os.sep, "Users", "gfelton", "Projects", "Toolbelt", "data", "output", "13132865405517656670_2.jpg")
    pano_to_perspective(file_name, "output_perspective.jpg")