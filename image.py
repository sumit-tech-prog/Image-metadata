#!/usr/bin/env python3
"""
ametadata_clean.py - focused CLI EXIF & image metadata extractor

Saves as: ametadata_clean.py

Purpose:
  Print only the most useful image/file metadata:
    - capture date/time (DateTimeOriginal preferred)
    - GPS (decimal) + Google Maps link
    - Camera / Mobile Make & Model
    - Image format, mode, width x height (pixels), frames, DPI
    - File size and filesystem timestamps (mtime fallback)
    - Exposure: ISO, ExposureTime, FNumber, FocalLength

Usage:
  python ametadata_clean.py image.jpg
  python ametadata_clean.py img1.jpg img2.png
  python ametadata_clean.py img.jpg -f json
  python ametadata_clean.py img.jpg -o out.json

Dependencies:
  pip install pillow exifread
"""

from __future__ import annotations
import argparse
import json
import os
import stat
import sys
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from PIL import Image, PngImagePlugin
except Exception:
    print("Please install Pillow: pip install pillow", file=sys.stderr)
    sys.exit(1)

try:
    import exifread
except Exception:
    exifread = None

# ---------------- utilities ----------------
def human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for unit in ['KB','MB','GB','TB']:
        n /= 1024.0
        if n < 1024.0:
            return f"{n:.2f} {unit}"
    return f"{n:.2f} PB"

def human_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).isoformat(sep=' ')
    except Exception:
        return str(ts)

def rational_to_float(r):
    """Convert exifread Ratio-like or numeric-like to float safely."""
    try:
        # exifread.utils.Ratio
        if hasattr(r, 'num') and hasattr(r, 'den'):
            if r.den == 0:
                return 0.0
            return float(r.num) / float(r.den)
        if isinstance(r, (list, tuple)):
            return [rational_to_float(x) for x in r]
        return float(r)
    except Exception:
        try:
            return float(str(r))
        except Exception:
            return None

def dms_to_decimal(dms, ref=None):
    """Convert [deg, min, sec] to decimal degrees with ref N/S/E/W handling."""
    try:
        if not dms or len(dms) < 3:
            return None
        deg = rational_to_float(dms[0])
        minute = rational_to_float(dms[1])
        sec = rational_to_float(dms[2])
        if deg is None or minute is None or sec is None:
            return None
        dec = deg + (minute / 60.0) + (sec / 3600.0)
        if ref and str(ref).upper() in ('S','W'):
            dec = -dec
        return round(dec, 7)
    except Exception:
        return None

# ---------------- extractors ----------------
def filesystem_info(path: str) -> Dict[str, Any]:
    st = os.stat(path)
    return {
        'path': os.path.abspath(path),
        'size_bytes': st.st_size,
        'size_human': human_size(st.st_size),
        'mtime': human_ts(st.st_mtime),
        'atime': human_ts(st.st_atime),
        'ctime': human_ts(st.st_ctime),
    }

def pillow_info(path: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    try:
        with Image.open(path) as im:
            info['format'] = im.format
            info['mode'] = im.mode
            info['width'] = im.width
            info['height'] = im.height
            info['frames'] = getattr(im, "n_frames", 1)
            # DPI if present
            dpi = im.info.get('dpi') or im.info.get('DPI')
            if dpi:
                try:
                    # DPI can be tuple (x, y) or single value
                    if isinstance(dpi, (list, tuple)):
                        info['dpi'] = {'x': dpi[0], 'y': dpi[1] if len(dpi) > 1 else dpi[0]}
                    else:
                        info['dpi'] = {'x': dpi, 'y': dpi}
                except Exception:
                    info['dpi'] = str(dpi)
            # Some PNG textual chunks
            if isinstance(im, PngImagePlugin.PngImageFile):
                # copy textual keys for possible camera-made tags (tEXt)
                txt = {}
                for k, v in im.info.items():
                    if isinstance(v, (str, int, float, list, dict)):
                        txt[k] = v
                if txt:
                    info['png_info'] = txt
    except Exception as e:
        info['error'] = f"Pillow error: {e}"
    return info

def exifread_tags(path: str) -> Optional[Dict[str, str]]:
    if not exifread:
        return None
    try:
        with open(path, 'rb') as fh:
            tags = exifread.process_file(fh, details=False)
        return {k: str(v) for k, v in tags.items()}
    except Exception:
        return None

def parse_friendly_exif(tags: Dict[str, Any]) -> Dict[str, Any]:
    """Pick friendly fields from exifread tags dict (strings)."""
    out: Dict[str, Any] = {}

    # Date/time: prefer EXIF DateTimeOriginal
    dt_keys = ['EXIF DateTimeOriginal', 'EXIF DateTimeDigitized', 'Image DateTime']
    capture_dt = None
    for k in dt_keys:
        if k in tags:
            capture_dt = tags[k]
            break
    out['capture_datetime'] = capture_dt

    # Camera / device
    make = tags.get('Image Make') or tags.get('Make')
    model = tags.get('Image Model') or tags.get('Model')
    if make or model:
        out['device'] = " ".join([str(x).strip() for x in (make, model) if x])

    # Exposure details
    iso = tags.get('EXIF ISOSpeedRatings') or tags.get('PhotographicSensitivity')
    exposure = tags.get('EXIF ExposureTime') or tags.get('ExposureTime')
    fnumber = tags.get('EXIF FNumber') or tags.get('FNumber')
    focal = tags.get('EXIF FocalLength') or tags.get('FocalLength')
    if iso:
        out['ISO'] = iso
    if exposure:
        out['ExposureTime'] = exposure
    if fnumber:
        out['Aperture'] = fnumber
    if focal:
        out['FocalLength'] = focal

    # GPS
    lat_tag = 'GPS GPSLatitude'
    lon_tag = 'GPS GPSLongitude'
    lat_ref_tag = 'GPS GPSLatitudeRef'
    lon_ref_tag = 'GPS GPSLongitudeRef'
    if lat_tag in tags and lon_tag in tags:
        try:
            # need to parse raw values into rationals if possible
            # exifread string for GPS is like "[deg, min, sec]" or comes from .values in earlier functions,
            # but here tags are strings — try to re-open with exifread to get .values if needed.
            # For robust parsing, we'll re-run exifread.process_file and inspect values (caller can pass original tag objects).
            # This function assumes caller passed strings; we'll try to parse simple numeric formats:
            raw_lat = tags[lat_tag]
            raw_lon = tags[lon_tag]
            # Try parse format like "[12, 34, 56/1]" or "12 34 56"
            def parse_component(comp_str):
                # comp_str may be like '12/1' or '56/100' or '12'
                comp_str = comp_str.strip()
                if '/' in comp_str:
                    num, den = comp_str.split('/', 1)
                    try:
                        return float(num) / float(den)
                    except Exception:
                        return None
                try:
                    return float(comp_str)
                except Exception:
                    return None
            import re
            # extract numbers
            lat_nums = re.findall(r'(-?\d+/\d+|-?\d+\.\d+|-?\d+)', str(raw_lat))
            lon_nums = re.findall(r'(-?\d+/\d+|-?\d+\.\d+|-?\d+)', str(raw_lon))
            if len(lat_nums) >= 3 and len(lon_nums) >= 3:
                lat_list = [parse_component(x) for x in lat_nums[:3]]
                lon_list = [parse_component(x) for x in lon_nums[:3]]
                lat_ref = tags.get(lat_ref_tag)
                lon_ref = tags.get(lon_ref_tag)
                lat_dec = dms_to_decimal(lat_list, lat_ref)
                lon_dec = dms_to_decimal(lon_list, lon_ref)
                if lat_dec is not None and lon_dec is not None:
                    out['gps'] = {'lat': lat_dec, 'lon': lon_dec,
                                  'google_maps': f"https://www.google.com/maps/search/?api=1&query={lat_dec},{lon_dec}"}
        except Exception:
            pass

    return out

# ---------------- presentation ----------------
def summarize_one(path: str) -> Dict[str, Any]:
    """Gather all focused metadata for a single file."""
    result: Dict[str, Any] = {}
    # filesystem
    try:
        result['filesystem'] = filesystem_info(path)
    except Exception as e:
        result['filesystem'] = {'error': str(e)}

    # Pillow info
    result['image'] = pillow_info(path)

    # exifread tags (raw strings) if available
    tags = exifread_tags(path) if exifread else None
    result['exif_tags'] = tags

    # friendly parsed exif
    if tags:
        result['exif_friendly'] = parse_friendly_exif(tags)
    else:
        result['exif_friendly'] = {}

    # If capture datetime missing in EXIF, fallback to file mtime
    if not result['exif_friendly'].get('capture_datetime'):
        result['exif_friendly']['capture_datetime'] = result['filesystem'].get('mtime')

    # Try to fill device name from PNG textual chunks if not in EXIF
    if not result['exif_friendly'].get('device') and isinstance(result['image'].get('png_info'), dict):
        # common PNG textual keys: Software, Description, Comment, Source, Creator
        for k in ('Software','Author','Description','Source','Creator','Creation Time'):
            if k in result['image']['png_info']:
                result['exif_friendly']['device'] = str(result['image']['png_info'][k])
                break

    return result

def print_clean(result: Dict[str, Any], path: str):
    fs = result.get('filesystem', {})
    img = result.get('image', {})
    exf = result.get('exif_friendly', {})

    print("="*72)
    print(f"File: {fs.get('path', path)}")
    print(f"File size : {fs.get('size_bytes')} bytes ({fs.get('size_human')})")
    print(f"Modified  : {fs.get('mtime')}")
    print("-"*72)
    # Image basic
    print("Image info:")
    print(f"  Format : {img.get('format')}")
    print(f"  Mode   : {img.get('mode')}")
    print(f"  Pixels : {img.get('width')} x {img.get('height')}")
    print(f"  Frames : {img.get('frames')}")
    if 'dpi' in img:
        dpi = img['dpi']
        if isinstance(dpi, dict):
            print(f"  DPI    : {dpi.get('x')} x {dpi.get('y')}")
        else:
            print(f"  DPI    : {dpi}")
    print("-"*72)
    # Capture / device
    print("Capture & device:")
    print(f"  Capture Date/Time : {exf.get('capture_datetime')}")
    print(f"  Device (Make/Model): {exf.get('device') or 'N/A'}")
    print("-"*72)
    # GPS
    gps = exf.get('gps')
    if gps:
        print("Location (GPS):")
        print(f"  Latitude : {gps.get('lat')}")
        print(f"  Longitude: {gps.get('lon')}")
        print(f"  Google Maps: {gps.get('google_maps')}")
    else:
        print("Location (GPS): Not found")
    print("-"*72)
    # Exposure details
    has_exposure = any(k in exf for k in ('ISO','ExposureTime','Aperture','FocalLength'))
    if has_exposure:
        print("Exposure / lens:")
        if 'ISO' in exf:
            print(f"  ISO         : {exf['ISO']}")
        if 'ExposureTime' in exf:
            print(f"  Exposure    : {exf['ExposureTime']}")
        if 'Aperture' in exf:
            print(f"  Aperture    : {exf['Aperture']}")
        if 'FocalLength' in exf:
            print(f"  FocalLength : {exf['FocalLength']}")
    else:
        print("Exposure / lens: Not available")
    print("="*72)

# ---------------- CLI ----------------
def main():
    parser = argparse.ArgumentParser(description="Focused image metadata extractor (clean output)")
    parser.add_argument('images', nargs='+', help="image file(s) to inspect")
    parser.add_argument('-f', '--format', choices=['text','json'], default='text', help="output format")
    parser.add_argument('-o', '--output', metavar='FILE', help="write JSON output to file")
    args = parser.parse_args()

    all_results = {}
    for p in args.images:
        if not os.path.exists(p):
            print(f"File not found: {p}", file=sys.stderr)
            all_results[p] = {'error': 'file not found'}
            continue
        res = summarize_one(p)
        all_results[p] = res

    if args.format == 'json' or args.output:
        out = all_results
        if args.output:
            try:
                with open(args.output,'w',encoding='utf-8') as fh:
                    json.dump(out, fh, indent=2, ensure_ascii=False)
                print(f"JSON saved to: {args.output}")
            except Exception as e:
                print(f"Failed to save JSON: {e}", file=sys.stderr)
                sys.exit(2)
        else:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    # default: text
    for path, res in all_results.items():
        if isinstance(res, dict) and res.get('error'):
            print(f"{path}: {res.get('error')}", file=sys.stderr)
            continue
        print_clean(res, path)

if __name__ == '__main__':
    main()
