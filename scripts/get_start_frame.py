import sys
import os
import subprocess

if len(sys.argv) < 2:
    print("Usage: python get_start_frame.py path/to/your/video/file.mp4")
    sys.exit()

video_file = sys.argv[1]

if not os.path.exists(video_file):
    print(f"File not found: {video_file}")
    sys.exit()

# Get the directory where the script is located (should be scripts/)
script_dir = os.path.dirname(os.path.abspath(__file__))
# Go up one level to get the project root, then into data/output
base_output_dir = os.path.join(os.path.dirname(script_dir), 'data', 'output')

# Get video filename without extension
video_basename = os.path.splitext(os.path.basename(video_file))[0]

# Create the full output directory: data/output/video_file_name/frames/
output_dir = os.path.join(base_output_dir, video_basename, 'frames')
os.makedirs(output_dir, exist_ok=True)

# Update output path for frames
out_name = f"{video_basename}_start_frame.jpg"
output_path = os.path.join(output_dir, out_name)

print(f"Extracting first frame of: {video_file}")
print(f"Output directory: {output_dir}")

cmd = ["ffmpeg", "-i", video_file, "-vf", "select=eq(n\,0)", "-vframes", "1", output_path]

try:
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"Subprocess result: {result.stderr}")
    
    if result.returncode == 0:
        print("Frame extraction completed successfully!")
    else:
        print(f"Error running ffmpeg: {result.stderr}")
        sys.exit(1)
        
except FileNotFoundError:
    print("Error: ffmpeg not found. Please make sure ffmpeg is installed and in your PATH.")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)