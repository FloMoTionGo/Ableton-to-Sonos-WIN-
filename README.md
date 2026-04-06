# Ableton to Sonos Streamer

Stream audio from Ableton Live to Sonos speakers over your local network using Python.

## How It Works

Ableton outputs to a virtual audio cable. Python captures that audio, serves it as a WAV stream on a local web server, and tells your Sonos speaker to play from it. Other Sonos speakers can group onto the target speaker through the Sonos app to hear the stream in multiple rooms.

## Requirements

- Windows PC
- Python 3.10+
- Ableton Live
- Sonos speaker(s) on the same network as your PC
- [VB-Cable](https://vb-audio.com/Cable/) (free virtual audio cable)
- [ASIO4ALL](https://www.asio4all.org/) (free ASIO driver)

## Install

1. Install VB-Cable from the link above and restart your PC.
2. Install Python dependencies:

```
pip install sounddevice numpy soco
```

## Audio Routing Setup

1. Open Ableton and go to **Options > Preferences > Audio**.
2. Set **Driver Type** to ASIO and select **ASIO4ALL v2**.
3. Open the ASIO4ALL control panel (wrench icon in Ableton’s audio prefs).
4. Enable **Virtual Cable 1** as an output under the Virtual Audio Cable section.
5. Disable any other output devices you don’t need.

If you want to monitor on headphones while streaming to Sonos, enable your Realtek output alongside VB-Cable in ASIO4ALL. Set Ableton’s **Master Out** to the VB-Cable channels and **Cue Out** to the Realtek channels.

## Sonos Stereo Pair (Optional)

If you want left/right stereo from two speakers, pair them in the Sonos app first:

**Settings > System > (pick a room) > Create Stereo Pair**

This is handled entirely by Sonos. The script just targets one logical speaker.

## Run

```
python Ableton2Sonos.py
```

The script will:

1. Find VB-Cable automatically
2. Detect your PC’s local IP
3. Start a WAV stream server on port 8090
4. Discover your Sonos speakers
5. Start playback on the first speaker found

Play something in Ableton and you should hear it on your Sonos speakers.

## Configuration

At the top of the script there are a few things you can change:

- **TARGET_SPEAKER** - Set to a speaker name like `"Living Room"` to target a specific speaker. Leave as `None` to auto-select the first one found.
- **STREAM_PORT** - HTTP port for the stream server. Default is 8090.
- **CHUNK_FRAMES** - Audio capture chunk size. Smaller = lower latency but more CPU. Default is 256.

## Multi-Room

The script sends audio to one speaker. To hear it in other rooms, open the Sonos app and group additional rooms onto the target speaker. Sonos handles syncing everything internally.

## Latency

There is roughly 1-2 seconds of delay. This is caused by Sonos’s internal firmware buffering and cannot be reduced through software. The delay is consistent, so you can work around it by triggering clips slightly early.

## Troubleshooting

**No speakers found** - Make sure your PC and Sonos are on the same subnet. Check that Windows Firewall allowed Python when it prompted.

**No audio** - Open `http://localhost:8090/stream.wav` in a browser. If you hear audio there, the capture is working and the issue is Sonos reaching your PC (firewall). If you hear nothing, check your ASIO4ALL routing.

**ConnectionResetError in the console** - Normal. Sonos probes the stream before settling into a stable connection. Playback still works.

**Wrong network adapter detected** - If `get_local_ip()` grabs a VPN or wrong adapter, hardcode your LAN IP in the script.
