#!/bin/bash
rm -rf build dist __pycache__
~/AppData/Local/python-3.9.12-embed-amd64/python.exe -m PyInstaller --onefile --windowed --debug=all --add-data "templates;templates" --add-data "scripts;scripts" --add-data "config.py;." app.py
