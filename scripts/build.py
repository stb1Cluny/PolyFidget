"""Build a ready-to-install PolyFidget zip into ./build.

Usage:
    python scripts/build.py [--blender PATH]

Runs Blender's own extension tools (validate, then build), so the zip is
exactly what "Install from Disk" expects. Blender is found from --blender,
then the BLENDER environment variable, then PATH, then the default Windows
install location.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "poly_fidget")
BUILD = os.path.join(ROOT, "build")
DEFAULT_BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"


def find_blender(explicit):
    for candidate in (explicit, os.environ.get("BLENDER"), shutil.which("blender"),
                      DEFAULT_BLENDER):
        if candidate and os.path.isfile(candidate):
            return candidate
    sys.exit("Blender not found: pass --blender PATH or set the BLENDER environment variable")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--blender", help="path to the Blender executable")
    args = parser.parse_args()
    blender = find_blender(args.blender)

    with open(os.path.join(SOURCE, "blender_manifest.toml"), "rb") as f:
        manifest = tomllib.load(f)
    zip_path = os.path.join(BUILD, f"{manifest['id']}-{manifest['version']}.zip")

    os.makedirs(BUILD, exist_ok=True)
    if os.path.exists(zip_path):
        os.remove(zip_path)   # Blender refuses to overwrite an existing zip

    cmd = [blender, "--factory-startup", "--command", "extension"]
    subprocess.run(cmd + ["validate", SOURCE], check=True)
    subprocess.run(cmd + ["build", "--source-dir", SOURCE, "--output-dir", BUILD], check=True)
    if not os.path.isfile(zip_path):
        sys.exit(f"Build finished but {zip_path} is missing")
    print(f"Built {os.path.relpath(zip_path, ROOT)} ({os.path.getsize(zip_path):,} bytes)")


if __name__ == "__main__":
    main()
