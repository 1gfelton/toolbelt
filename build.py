#!/usr/bin/env python3
"""
Build script for Payette Toolbelt desktop application
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def clean_build():
    """Remove previous build artifacts"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Cleaned {dir_name}/")

def check_requirements():
    """Verify all dependencies are installed"""
    try:
        import flask
        import flaskwebgui
        print("✓ Core dependencies found")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def build_executable():
    """Build the desktop application"""
    print("Building desktop application...")
    
    # Run PyInstaller
    cmd = [sys.executable, '-m', 'PyInstaller', 'build.spec', '--clean']
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ Build completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Build failed: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False

def create_installer_script():
    """Create a simple installer script"""
    installer_content = '''@echo off
echo Installing Payette Toolbelt...
if not exist "C:\\Program Files\\PayetteToolbelt" mkdir "C:\\Program Files\\PayetteToolbelt"
copy "PayetteToolbelt.exe" "C:\\Program Files\\PayetteToolbelt\\"
echo Creating desktop shortcut...
echo Set oWS = WScript.CreateObject("WScript.Shell") > CreateShortcut.vbs
echo sLinkFile = "%USERPROFILE%\\Desktop\\Payette Toolbelt.lnk" >> CreateShortcut.vbs
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> CreateShortcut.vbs
echo oLink.TargetPath = "C:\\Program Files\\PayetteToolbelt\\PayetteToolbelt.exe" >> CreateShortcut.vbs
echo oLink.Save >> CreateShortcut.vbs
cscript CreateShortcut.vbs
del CreateShortcut.vbs
echo Installation complete!
pause
'''
    
    with open('dist/install.bat', 'w') as f:
        f.write(installer_content)
    print("✓ Created installer script: dist/install.bat")

def main():
    print("=== Payette Toolbelt Build Script ===")
    
    if not check_requirements():
        sys.exit(1)
    
    clean_build()
    
    if not build_executable():
        sys.exit(1)
    
    create_installer_script()
    
    print("\n=== Build Complete ===")
    print("Executable: dist/PayetteToolbelt.exe")
    print("Installer: dist/install.bat")
    print("Ready for corporate deployment!")

if __name__ == "__main__":
    main()