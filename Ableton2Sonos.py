# “””
Ableton → Sonos LOW-LATENCY Streamer

Streams raw PCM (WAV) instead of MP3 to eliminate encoder latency.
Uses minimal chunk sizes and a lean HTTP server.

The remaining ~1-2s latency is Sonos firmware buffering — unavoidable
for HTTP streams. For sub-100ms you’d need Sonos Line-In on a Port/Five.

Setup:
pip install sounddevice numpy soco
(no more lameenc needed)
“””

import sounddevice as sd
import numpy as np
import soco
import socket
import struct
import threading
import queue
import time
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

# ─── Configuration ───────────────────────────────────────────────

SAMPLE_RATE = 44100
CHANNELS = 2
BITS_PER_SAMPLE = 16
CHUNK_FRAMES = 256         # ~6ms per chunk (down from 1024)
STREAM_PORT = 8090

TARGET_SPEAKER = None      # e.g. “Living Room” or None for auto

# ─── Find VB-Cable ───────────────────────────────────────────────

def find_vb_cable():
devices = sd.query_devices()
for i, dev in enumerate(devices):
if ‘cable’ in dev[‘name’].lower() and dev[‘max_input_channels’] >= 2:
print(f”  Found VB-Cable: [{i}] {dev[‘name’]}”)
return i
print(”  VB-Cable not found! Available inputs:”)
for i, dev in enumerate(devices):
if dev[‘max_input_channels’] > 0:
print(f”    [{i}] {dev[‘name’]}”)
sys.exit(1)

def get_local_ip():
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
s.connect((“10.0.0.1”, 80))
return s.getsockname()[0]
finally:
s.close()

# ─── Audio capture ───────────────────────────────────────────────

audio_q = queue.Queue(maxsize=500)

def audio_callback(indata, frames, time_info, status):
if status:
print(f”  audio: {status}”)
try:
# Convert to int16 immediately in the callback to minimize
# work on the serving thread
pcm = (indata * 32767).astype(np.int16).tobytes()
audio_q.put_nowait(pcm)
except queue.Full:
pass  # drop rather than block

# ─── WAV header for “infinite” streaming ─────────────────────────

def make_wav_header():
“””
Standard WAV header with size fields set to max (0xFFFFFFFF).
Sonos reads the header, then consumes the endless PCM data stream.
“””
byte_rate = SAMPLE_RATE * CHANNELS * (BITS_PER_SAMPLE // 8)
block_align = CHANNELS * (BITS_PER_SAMPLE // 8)
# Use 0xFFFFFFFF for data size to signal “streaming / unknown length”
data_size = 0xFFFFFFFF
file_size = data_size + 36  # will overflow but that’s fine for streaming

```
header = struct.pack('<4sI4s', b'RIFF', file_size & 0xFFFFFFFF, b'WAVE')
fmt = struct.pack('<4sIHHIIHH',
    b'fmt ', 16,           # chunk size
    1,                     # PCM format
    CHANNELS,
    SAMPLE_RATE,
    byte_rate,
    block_align,
    BITS_PER_SAMPLE,
)
data_hdr = struct.pack('<4sI', b'data', data_size & 0xFFFFFFFF)
return header + fmt + data_hdr
```

# ─── Lean HTTP server (no Flask overhead) ────────────────────────

class StreamHandler(BaseHTTPRequestHandler):
“”“Minimal HTTP handler — serves WAV stream or handles HEAD requests.”””

```
def do_HEAD(self):
    self.send_response(200)
    self.send_header('Content-Type', 'audio/wav')
    self.send_header('Connection', 'keep-alive')
    self.send_header('Cache-Control', 'no-cache, no-store')
    self.send_header('icy-name', 'Ableton Stream')
    self.end_headers()

def do_GET(self):
    if self.path != '/stream.wav':
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Ableton streamer running. Stream at /stream.wav')
        return

    self.send_response(200)
    self.send_header('Content-Type', 'audio/wav')
    self.send_header('Connection', 'keep-alive')
    self.send_header('Cache-Control', 'no-cache, no-store')
    self.send_header('Transfer-Encoding', 'chunked')
    self.end_headers()

    # Send WAV header first
    wav_hdr = make_wav_header()
    self._send_chunk(wav_hdr)

    # Then stream raw PCM forever
    silence = b'\x00' * (CHUNK_FRAMES * CHANNELS * (BITS_PER_SAMPLE // 8))

    try:
        while True:
            try:
                pcm = audio_q.get(timeout=2)
            except queue.Empty:
                pcm = silence
            self._send_chunk(pcm)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass  # Sonos disconnected — that's fine

def _send_chunk(self, data):
    """Send a single HTTP chunked-transfer chunk."""
    chunk = f"{len(data):X}\r\n".encode() + data + b"\r\n"
    self.wfile.write(chunk)
    self.wfile.flush()

def log_message(self, format, *args):
    # Quieter logging — only print connections/disconnections
    if 'GET /stream.wav' in (args[0] if args else ''):
        print(f"  Sonos connected: {self.client_address[0]}")
```

# ─── Sonos control ──────────────────────────────────────────────

def start_sonos(stream_url):
print(”\n  Discovering Sonos…”)
discovered = soco.discover(timeout=10)
if not discovered:
print(”  No Sonos speakers found!”)
sys.exit(1)

```
speakers = {s.player_name: s for s in discovered}
print(f"  Found: {list(speakers.keys())}")

if TARGET_SPEAKER and TARGET_SPEAKER in speakers:
    target = speakers[TARGET_SPEAKER]
else:
    target = list(speakers.values())[0]

coordinator = target.group.coordinator
print(f"  Target: {coordinator.player_name}")

coordinator.play_uri(stream_url, title="Ableton Live")
print(f"  Playback started!")
return coordinator
```

# ─── Main ────────────────────────────────────────────────────────

def main():
print(”=” * 50)
print(”  Ableton → Sonos (Low-Latency WAV)”)
print(”=” * 50)

```
device_idx = find_vb_cable()
local_ip = get_local_ip()
stream_url = f"http://{local_ip}:{STREAM_PORT}/stream.wav"

print(f"\n  PC IP: {local_ip}")
print(f"  Stream: {stream_url}")
print(f"  Chunk: {CHUNK_FRAMES} frames ({CHUNK_FRAMES/SAMPLE_RATE*1000:.1f}ms)")

# Start audio capture
print("\n  Starting audio capture...")
audio_stream = sd.InputStream(
    device=device_idx,
    samplerate=SAMPLE_RATE,
    channels=CHANNELS,
    blocksize=CHUNK_FRAMES,
    dtype='float32',
    callback=audio_callback,
    latency='low',         # request lowest latency from OS
)
audio_stream.start()

# Start HTTP server
print(f"  Starting WAV stream server on :{STREAM_PORT}...")
server = HTTPServer(('0.0.0.0', STREAM_PORT), StreamHandler)
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()
time.sleep(0.5)

# Sonos playback
coordinator = start_sonos(stream_url)

print("\n" + "=" * 50)
print("  Streaming! Press Ctrl+C to stop.")
print("=" * 50 + "\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n  Stopping...")
    try:
        coordinator.stop()
    except Exception:
        pass
    audio_stream.stop()
    audio_stream.close()
    server.shutdown()
    print("  Done.")
```

if **name** == ‘**main**’:
main()
