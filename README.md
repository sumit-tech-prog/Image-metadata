 Image Metadata Extractor (CLI Version)
A clean and accurate EXIF & image metadata extraction tool for Kali Linux, OSINT, and Cybersecurity Projects.

![Python](https://img.shields.io/badge/Python-3.x-blue)
![Kali Linux](https://img.shields.io/badge/Kali-Linux-blueviolet)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Stable-success)

---

##Overview

`port.py` is a **terminal-based image metadata analyzer** that extracts **only** the important and meaningful information from images.

It is designed for:
- Cybersecurity students  
- OSINT investigators  
- Digital forensics labs  
- Privacy researchers  
- Anyone who wants clean EXIF data without noise

Runs directly in **Kali Linux terminal**.

---

Extracts the Most Useful Metadata
- **Capture date & time** (DateTimeOriginal)
- **GPS coordinates** (converted to decimal)
- **Clickable Google Maps link**
- **Camera / Mobile make & model**
- **Image format** (JPEG/PNG/HEIC/WEBP/etc.)
- **Resolution / Pixels**
- **Number of frames** (GIF/APNG)
- **DPI** (if available)

Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/Image-Metadata-Extractor.git
cd Image-Metadata-Extractor
```

### 2. Install Required Packages
```bash
pip install pillow exifread
```

### 3. Run the Tool
```bash
python ametadata_clean.py image.jpg
```

---

## 📚 Usage Guide

###  Analyze a Single Image
```bash
python ametadata_clean.py photo.jpg
```

### Analyze Multiple Images
```bash
python ametadata_clean.py *.jpg
```

###  Output JSON to Terminal
```bash
python ametadata_clean.py photo.jpg -f json
```

###  Save JSON Output to File
```bash
python ametadata_clean.py photo.jpg -o metadata.json
```

###  Combined Example
```bash
python ametadata_clean.py img1.jpg img2.png -f json -o all_meta.json
```
---

##  Example Output (Text Mode)

```
========================================================================
File: /home/user/photo.jpg
File size : 3252981 bytes (3.10 MB)
Modified  : 2025-11-18 11:21:45
------------------------------------------------------------------------
Image info:
  Format : JPEG
  Mode   : RGB
  Pixels : 4000 x 3000
  Frames : 1
  DPI    : 72 x 72
------------------------------------------------------------------------
Capture & device:
  Capture Date/Time : 2025:11:18 11:20:13
  Device (Make/Model): Samsung SM-A525F
------------------------------------------------------------------------
Location (GPS):
  Latitude : 19.123456
  Longitude: 72.987654
  Google Maps: https://www.google.com/maps/search/?api=1&query=19.123456,72.987654
------------------------------------------------------------------------
Exposure / lens:
  ISO         : 200
  Exposure    : 1/120
  Aperture    : f/1.8
  FocalLength : 5.4 mm
========================================================================

