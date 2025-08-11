from flask import Flask, jsonify, request, render_template, Response, stream_with_context, send_from_directory
from flaskwebgui import FlaskUI
import os
import subprocess
import sys
import json
import time
from werkzeug.utils import secure_filename
import tempfile
import shutil

from config import DESKTOP_CONFIG, CORPORATE_CONFIG, get_base_path, is_executable

app = Flask(__name__)

# Fix the path construction
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'scripts')
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'data', 'output')
ALLOWED_EXTENSIONS = ["mp4", "m4a", "gif", "mov", "webm"]
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'data', 'input')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def configure_for_desktop():
    """Configure flask settings for desktop"""
    if is_executable():
        # Running as packaged executable
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        app.config['TEMPLATES_AUTO_RELOAD'] = False
        
        # Ensure data directories exist in executable
        base_path = get_base_path()
        global OUTPUT_DIR, UPLOAD_FOLDER
        OUTPUT_DIR = os.path.join(os.path.expanduser('~'), 'PayetteToolbelt', 'output')
        UPLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'PayetteToolbelt', 'input')
        
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        print(f"Desktop mode: Data in {os.path.expanduser('~')}/PayetteToolbelt/")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/lookaround")
def lookaround_page():
    return render_template("lookaround.html")

@app.route("/list_dirs")
def list_dirs():
    root_path = os.path.abspath(os.path.dirname(__file__))
    dir_contents = {}
    for item in os.listdir(root_path):
        full_path = os.path.join(root_path, item)
        if os.path.isdir(full_path):
            dir_contents[item] = "directory"
        else:
            dir_contents[item] = "file"
    return jsonify(dir_contents)

# Add route to serve static panorama images
@app.route("/static/panoramas/<filename>")
def serve_panorama(filename):
    return send_from_directory(OUTPUT_DIR, filename)

@app.route("/stream_lookaround", methods=["GET"])
def stream_lookaround_data():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    num_panos = request.args.get("num_panos", "1")  # Default to 1 if not specified
    zoom = request.args.get("zoom_lvl", "2")

    if not lat or not lon:
        def error_response():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Latitude and longitude are required query parameters.'})}\n\n"
        return Response(error_response(), mimetype='text/event-stream')

    try:
        lat = float(lat)
        lon = float(lon)
        num_panos = int(num_panos)
        zoom = int(zoom)
        
        # Validate num_panos range
        if num_panos < 1 or num_panos > 500:
            raise ValueError("Number of panoramas must be between 1 and 50")
            
    except (ValueError, TypeError) as e:
        def error_response():
            yield f"data: {json.dumps({'type': 'error', 'message': f'Invalid parameters: {str(e)}'})}\n\n"
        return Response(error_response(), mimetype='text/event-stream')

    script_name = "get_lookaround"
    script_path = os.path.join(SCRIPTS_DIR, script_name + '.py')

    if not os.path.exists(script_path):
        def error_response():
            error_msg = f"Script '{script_name}.py' not found in {SCRIPTS_DIR}."
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
        return Response(error_response(), mimetype='text/event-stream')

    def generate():
        process = None
        saved_filenames = []

        try:
            # Pass the number of panoramas as the third argument
            process = subprocess.Popen(
                [sys.executable, script_path, str(lat), str(lon), str(num_panos)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0
            )

            from threading import Thread
            from queue import Queue, Empty

            q_stdout = Queue()
            q_stderr = Queue()

            def enqueue_output(out, queue):
                for line in iter(out.readline, ''):
                    queue.put(line)
                out.close()

            t_stdout = Thread(target=enqueue_output, args=(process.stdout, q_stdout))
            t_stderr = Thread(target=enqueue_output, args=(process.stderr, q_stderr))

            t_stdout.daemon = True
            t_stderr.daemon = True
            t_stdout.start()
            t_stderr.start()

            while process.poll() is None or not q_stdout.empty() or not q_stderr.empty():
                try:
                    line = q_stdout.get_nowait()
                    # Look for saved panorama output
                    if "Saved equirectangular panorama:" in line:
                        # Extract filename from the output
                        saved_path = line.split("Saved equirectangular panorama:")[-1].strip()
                        saved_filename = os.path.basename(saved_path)
                        saved_filenames.append(saved_filename)
                        
                        # Try to extract panorama ID from the filename
                        pano_id = saved_filename.split('_')[0] if '_' in saved_filename else saved_filename.split('.')[0]
                        
                        yield f"data: {json.dumps({'type': 'saved_image', 'path': saved_filename, 'pano_id': pano_id})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'stdout', 'message': line})}\n\n"
                    print(f"[SCRIPT-STDOUT] {line.strip()}")
                except Empty:
                    pass

                try:
                    line = q_stderr.get_nowait()
                    yield f"data: {json.dumps({'type': 'stderr', 'message': line})}\n\n"
                    print(f"[SCRIPT-STDERR] {line.strip()}")
                except Empty:
                    pass

                time.sleep(0.01)

            process.wait()

            if process.returncode == 0:
                yield f"data: {json.dumps({'type': 'script_end', 'status': 'success', 'image_paths': saved_filenames, 'total_images': len(saved_filenames)})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'script_end', 'status': 'failure', 'code': process.returncode})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'app_error', 'message': str(e)})}\n\n"
            print(f"[APPLICATION_ERROR] {str(e)}", file=sys.stderr)
            if process:
                process.kill()
        finally:
            if 't_stdout' in locals() and t_stdout.is_alive():
                t_stdout.join(timeout=1)
            if 't_stderr' in locals() and t_stderr.is_alive():
                t_stderr.join(timeout=1)

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route("/stream_streetview", methods=["GET"])
def stream_streetview_data():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    num_panos = request.args.get("num_panos", "1")  # Default to 1 if not specified
    zoom = request.args.get("zoom_lvl", "2")

    if not lat or not lon:
        def error_response():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Latitude and longitude are required query parameters.'})}\n\n"
        return Response(error_response(), mimetype='text/event-stream')

    try:
        lat = float(lat)
        lon = float(lon)
        num_panos = int(num_panos)
        zoom = int(zoom)
        
        # Validate num_panos range
        if num_panos < 1 or num_panos > 500:
            raise ValueError("Number of panoramas must be between 1 and 500")
            
    except (ValueError, TypeError) as e:
        def error_response():
            yield f"data: {json.dumps({'type': 'error', 'message': f'Invalid parameters: {str(e)}'})}\n\n"
        return Response(error_response(), mimetype='text/event-stream')

    script_name = "get_streetview"
    script_path = os.path.join(SCRIPTS_DIR, script_name + '.py')

    if not os.path.exists(script_path):
        def error_response():
            error_msg = f"Script '{script_name}.py' not found in {SCRIPTS_DIR}."
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
        return Response(error_response(), mimetype='text/event-stream')

    def generate():
        process = None
        saved_filenames = []

        try:
            # Pass the number of panoramas as the third argument
            process = subprocess.Popen(
                [sys.executable, script_path, str(lat), str(lon), str(num_panos)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0
            )

            from threading import Thread
            from queue import Queue, Empty

            q_stdout = Queue()
            q_stderr = Queue()

            def enqueue_output(out, queue):
                for line in iter(out.readline, ''):
                    queue.put(line)
                out.close()

            t_stdout = Thread(target=enqueue_output, args=(process.stdout, q_stdout))
            t_stderr = Thread(target=enqueue_output, args=(process.stderr, q_stderr))

            t_stdout.daemon = True
            t_stderr.daemon = True
            t_stdout.start()
            t_stderr.start()

            while process.poll() is None or not q_stdout.empty() or not q_stderr.empty():
                try:
                    line = q_stdout.get_nowait()
                    # Look for saved panorama output
                    if "Saved streetview panorama:" in line:
                        # Extract filename from the output
                        saved_path = line.split("Saved streetview pano to ")[-1].strip()
                        print(f"[stream_streetview_data] saved_path: {saved_path}")
                        saved_filename = os.path.basename(saved_path)
                        saved_filenames.append(saved_filename)
                        
                        # Try to extract panorama ID from the filename
                        pano_id = saved_filename.split('_')[0] if '_' in saved_filename else saved_filename.split('.')[0]
                        
                        yield f"data: {json.dumps({'type': 'saved_image', 'path': saved_filename, 'pano_id': pano_id})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'stdout', 'message': line})}\n\n"
                    print(f"[SCRIPT-STDOUT] {line.strip()}")
                except Empty:
                    pass

                try:
                    line = q_stderr.get_nowait()
                    yield f"data: {json.dumps({'type': 'stderr', 'message': line})}\n\n"
                    print(f"[SCRIPT-STDERR] {line.strip()}")
                except Empty:
                    pass

                time.sleep(0.01)

            process.wait()

            if process.returncode == 0:
                yield f"data: {json.dumps({'type': 'script_end', 'status': 'success', 'image_paths': saved_filenames, 'total_images': len(saved_filenames)})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'script_end', 'status': 'failure', 'code': process.returncode})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'app_error', 'message': str(e)})}\n\n"
            print(f"[APPLICATION_ERROR] {str(e)}", file=sys.stderr)
            if process:
                process.kill()
        finally:
            if 't_stdout' in locals() and t_stdout.is_alive():
                t_stdout.join(timeout=1)
            if 't_stderr' in locals() and t_stderr.is_alive():
                t_stderr.join(timeout=1)

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route("/video_tools", methods=["GET", "POST"])
def stream_converter():
    return render_template("video_tools.html")

@app.route("/upload_video", methods=["POST"])
def upload_video():
    if 'video' not in request.files:
        return Response(
            f"data: {json.dumps({'type': 'error', 'message': 'No video file provided'})}\n\n",
            mimetype='text/event-stream'
        )
    
    file = request.files['video']
    if file.filename == '':
        return Response(
            f"data: {json.dumps({'type': 'error', 'message': 'No file selected'})}\n\n",
            mimetype='text/event-stream'
        )
    
    if not allowed_file(file.filename):
        return Response(
            f"data: {json.dumps({'type': 'error', 'message': 'Invalid file type. Allowed: mp4, avi, mov, mkv, wmv, flv, webm'})}\n\n",
            mimetype='text/event-stream'
        )

    def generate():
        temp_file_path = None
        process = None
        
        try:
            # Save uploaded file temporarily
            filename = secure_filename(file.filename)
            temp_file_path = os.path.join(OUTPUT_DIR, filename)
            file.save(temp_file_path)
            
            yield f"data: {json.dumps({'type': 'stdout', 'message': f'File uploaded: {filename}\\n'})}\n\n"
            
            script_path = os.path.join(SCRIPTS_DIR, 'get_video_frames.py')
            
            if not os.path.exists(script_path):
                yield f"data: {json.dumps({'type': 'error', 'message': 'get_video_frames.py script not found'})}\n\n"
                return
            
            # Execute the script
            process = subprocess.Popen(
                [sys.executable, script_path, temp_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0
            )
            
            from threading import Thread
            from queue import Queue, Empty
            
            q_stdout = Queue()
            q_stderr = Queue()
            
            def enqueue_output(out, queue):
                for line in iter(out.readline, ''):
                    queue.put(line)
                out.close()
            
            t_stdout = Thread(target=enqueue_output, args=(process.stdout, q_stdout))
            t_stderr = Thread(target=enqueue_output, args=(process.stderr, q_stderr))
            
            t_stdout.daemon = True
            t_stderr.daemon = True
            t_stdout.start()
            t_stderr.start()
            
            while process.poll() is None or not q_stdout.empty() or not q_stderr.empty():
                try:
                    line = q_stdout.get_nowait()
                    yield f"data: {json.dumps({'type': 'stdout', 'message': line})}\n\n"
                except Empty:
                    pass
                
                try:
                    line = q_stderr.get_nowait()
                    yield f"data: {json.dumps({'type': 'stderr', 'message': line})}\n\n"
                except Empty:
                    pass
                
                time.sleep(0.01)
            
            process.wait()
            
            if process.returncode == 0:
                yield f"data: {json.dumps({'type': 'script_end', 'status': 'success'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'script_end', 'status': 'failure', 'code': process.returncode})}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'app_error', 'message': str(e)})}\n\n"
            if process:
                process.kill()
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if 't_stdout' in locals() and t_stdout.is_alive():
                t_stdout.join(timeout=1)
            if 't_stderr' in locals() and t_stderr.is_alive():
                t_stderr.join(timeout=1)
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route("/process_video", methods=["POST"])
def process_video():
    if 'video' not in request.files:
        return Response(
            f"data: {json.dumps({'type': 'error', 'message': 'No video file provided'})}\n\n",
            mimetype='text/event-stream'
        )
    
    if 'script' not in request.form:
        return Response(
            f"data: {json.dumps({'type': 'error', 'message': 'No script specified'})}\n\n",
            mimetype='text/event-stream'
        )
    
    file = request.files['video']
    script_name = request.form['script']
    
    if file.filename == '':
        return Response(
            f"data: {json.dumps({'type': 'error', 'message': 'No file selected'})}\n\n",
            mimetype='text/event-stream'
        )
    
    if not allowed_file(file.filename):
        return Response(
            f"data: {json.dumps({'type': 'error', 'message': 'Invalid file type. Allowed: mp4, avi, mov, mkv, wmv, flv, webm'})}\n\n",
            mimetype='text/event-stream'
        )

    def generate():
        temp_file_path = None
        process = None
        
        try:
            # Save uploaded file temporarily
            filename = secure_filename(file.filename)
            temp_file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(temp_file_path)
            
            yield f"data: {json.dumps({'type': 'stdout', 'message': f'File uploaded: {filename}\\n'})}\n\n"
            yield f"data: {json.dumps({'type': 'stdout', 'message': f'Running script: {script_name}\\n'})}\n\n"
            
            script_path = os.path.join(SCRIPTS_DIR, script_name + '.py')
            
            if not os.path.exists(script_path):
                yield f"data: {json.dumps({'type': 'error', 'message': f'{script_name}.py script not found'})}\n\n"
                return
            
            # Execute the script with the video file path
            process = subprocess.Popen(
                [sys.executable, script_path, temp_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0
            )
            
            from threading import Thread
            from queue import Queue, Empty
            
            q_stdout = Queue()
            q_stderr = Queue()
            
            def enqueue_output(out, queue):
                for line in iter(out.readline, ''):
                    queue.put(line)
                out.close()
            
            t_stdout = Thread(target=enqueue_output, args=(process.stdout, q_stdout))
            t_stderr = Thread(target=enqueue_output, args=(process.stderr, q_stderr))
            
            t_stdout.daemon = True
            t_stderr.daemon = True
            t_stdout.start()
            t_stderr.start()
            
            while process.poll() is None or not q_stdout.empty() or not q_stderr.empty():
                try:
                    line = q_stdout.get_nowait()
                    yield f"data: {json.dumps({'type': 'stdout', 'message': line})}\n\n"
                except Empty:
                    pass
                
                try:
                    line = q_stderr.get_nowait()
                    yield f"data: {json.dumps({'type': 'stderr', 'message': line})}\n\n"
                except Empty:
                    pass
                
                time.sleep(0.01)
            
            process.wait()
            
            if process.returncode == 0:
                yield f"data: {json.dumps({'type': 'script_end', 'status': 'success'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'script_end', 'status': 'failure', 'code': process.returncode})}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'app_error', 'message': str(e)})}\n\n"
            if process:
                process.kill()
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if 't_stdout' in locals() and t_stdout.is_alive():
                t_stdout.join(timeout=1)
            if 't_stderr' in locals() and t_stderr.is_alive():
                t_stderr.join(timeout=1)
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == "__main__":
    # Configure for desktop mode
    configure_for_desktop()
    # Create necessary directories
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    if not os.path.exists(SCRIPTS_DIR):
        os.makedirs(SCRIPTS_DIR)
    
    print(f"Scripts directory: {SCRIPTS_DIR}")
    print(f"Templates directory: {TEMPLATES_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")

    if CORPORATE_CONFIG['disable_dev_tools']:
        app.config['ENV'] = 'production'
        app.config['DEBUG'] = False

    ui = FlaskUI(
        app=app,
        server="flask",
        **DESKTOP_CONFIG,
    )
    
    #app.run(debug=True, host='0.0.0.0', port=5000)
    ui.run()