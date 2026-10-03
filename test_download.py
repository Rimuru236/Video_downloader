#!/usr/bin/env python3
"""Test script to verify YouTube download with database configuration."""
import os
import sys
import sqlite3
import yt_dlp

# Read configuration from database
conn = sqlite3.connect('streamvault.db')
cursor = conn.cursor()
cursor.execute('SELECT value FROM settings WHERE key = ?', ('default_quality',))
row = cursor.fetchone()
default_quality = row[0] if row else "bestvideo+bestaudio/best"
cursor.execute('SELECT value FROM settings WHERE key = ?', ('deno_path',))
row = cursor.fetchone()
deno_path = row[0] if row else ""
conn.close()

# Configure Deno runtime
js_runtimes = {}
if deno_path:
    js_runtimes["deno"] = {"path": deno_path}
else:
    js_runtimes["deno"] = {}

ydl_opts = {
    "format": "136+251-7",  # Test with the manually confirmed working format
    "outtmpl": "./downloads/%(title)s.%(ext)s",
    "js_runtimes": js_runtimes,
    "quiet": False,
    "no_warnings": False,
    "merge_output_format": "mp4",
}

url = "https://youtu.be/_46A8BQvqwE?si=C7xPE6SFrxaPnRlm"

print(f"Testing download with format: 136+251-7 (manual test)")
print(f"Deno path: {deno_path}")
print(f"js_runtimes config: {js_runtimes}")
print(f"URL: {url}")
print("-" * 80)

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print("-" * 80)
    print("SUCCESS: Download completed!")
except Exception as e:
    print("-" * 80)
    print(f"FAILED: {e}")
    sys.exit(1)
