# Windows Setup Guide

## IMPORTANT — Move out of OneDrive first

OneDrive tries to sync `node_modules` (100,000+ files with very long paths),
which causes RPC errors and install failures on Windows.

**Move the project folder to a non-OneDrive location before installing:**

```
C:\Projects\streamvault\     ✅ Good
C:\Users\USER\OneDrive\...   ❌ Will break
C:\Users\USER\Desktop\...    ❌ Desktop is synced by OneDrive by default
```

## Setup Steps

### 1. Move the project
```
Move universal-downloader\ to C:\Projects\streamvault\
```

### 2. Install backend
```cmd
cd C:\Projects\streamvault
pip install -r requirements.txt
```

### 3. Install FFmpeg (required for merging video+audio)
- Download from https://ffmpeg.org/download.html
- Extract and add `bin\` folder to your PATH

### 4. Install frontend
```cmd
cd C:\Projects\streamvault\frontend
npm install
npm run dev
```

### 5. Start backend (separate terminal)
```cmd
cd C:\Projects\streamvault\backend
python main.py
```

Open http://localhost:3000

## If you still get path errors

Run npm with a shorter cache path:
```cmd
npm install --cache C:\npm-cache
```

Or use the `--prefix` flag to control install location.
