import py360convert

def pano_to_perspective(input_path, output_path, fov=90, yaw=0, pitch=0):
    perspective_img = py360convert.e2p(
        input_path,
        fov_deg=(fov, fov),
        u_deg=yaw,
        v_deg=pitch,
        out_hw=(2048, 2048),
        in_rot_deg=0
    )
    
    # Save the result
    from PIL import Image
    if isinstance(perspective_img, str):
        # If e2p returns path, copy to desired location
        img = Image.open(perspective_img)
        img.save(output_path)
    else:
        # If e2p returns image array
        img = Image.fromarray(perspective_img)
        img.save(output_path)

if __name__ == "__main__":
    # Example usage
    pano_to_perspective("P:\Takeda\29200.00_585_3RDST_HQ\_DRAWINGS\_Revit\3D\_DesignVis\_Output\25_08-01_Signage Study\Working Files\Gaussian Images\View 04\panorama.jpg", "output_perspective.jpg")