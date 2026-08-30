import tkinter as tk
from tkinter import filedialog, simpledialog
import json
import os
import sys

# Fix for the OpenMP duplicate library error (common in Conda environments with PyTorch + OpenCV)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Prompt handed to the LLM. Plain (non-f) string with a __SONG_TITLE__ placeholder,
# so braces in the example JSON need no escaping.
PROMPT_TEMPLATE = """You are an expert generative artist and Python developer specializing in 1-bit demoscene graphics.
I am building a live procedural music visualizer for a monochrome OLED display (128x64 pixels, 1-bit color).
The visualizer is for the song '__SONG_TITLE__'.

I have a `timeline.json` mapping every lyric word and instrumental gap to exact millisecond timestamps.

YOUR TASK:
Write a Python file named `generated_visuals.py`. It MUST contain EXACTLY this function signature:
`def render_frame(current_time, current_event):`

- `current_time`: float, seconds elapsed since the song started.
- `current_event`: a dict from the timeline, e.g. `{"type": "word", "text": "Hello", "start": 12.4, "end": 12.9}` or `{"type": "gap", "start": ..., "end": ...}`. It may be `None` or `{}`, so begin with `if not current_event: current_event = {"type": "gap"}` and read every key with `.get()`.
- MUST return a `PIL.Image` in 'L' mode, exactly 128x64. Only values 0 (black) and 255 (white) may appear in the returned image.

=== THE CRITICAL PROBLEM YOU MUST SOLVE ===

My previous attempt failed and looked extremely repetitive. Here is exactly why, measured on the real timeline. Do not repeat these two mistakes:

MISTAKE 1 - The seed was derived from the word text alone.
This song has 461 words but only 104 unique ones; 92% of all words are repeats. The word "been" is sung 28 times. With a text-only seed, all 28 renders were pixel-identical, so every chorus was a literal replay of the same animation.
FIX: seed on the word AND its timestamp, so the same word looks different every time it is sung:
    seed = int(hashlib.md5((text + "|" + str(current_event.get("start", 0))).encode()).hexdigest()[:8], 16)
Derive every parameter from this `seed`.

MISTAKE 2 - There was only ONE effect, whose parameters were varied by the hash.
Varying node count, radius and rotation speed of a single spinning polygon does NOT produce visual variety. A 5-sided polygon at radius 18 and a 6-sided one at radius 24 are indistinguishable at 128x64. Random parameters are not interesting; STRUCTURAL change is.
FIX: write at least 12 SEPARATE render functions that produce structurally different KINDS of image, and dispatch on the seed:
    FAMILIES = [fx_plasma, fx_tunnel, fx_metaballs, ...]
    FAMILIES[seed % len(FAMILIES)](draw, img, seed, progress, current_time, text)

=== REQUIRED EFFECT FAMILIES (at least 12, one function each) ===
Each must be a genuinely different visual language, not a re-parameterisation:
1.  Full-screen dithered plasma / interference field (sine sums over the whole frame, no center symmetry)
2.  Perspective tunnel or concentric ripples rushing toward the viewer
3.  Metaballs / threshold blob field that merges and splits
4.  Rotating 3D wireframe solid with real perspective projection (cube, icosahedron, torus)
5.  Particle system with actual physics: gravity, velocity, bounce off the frame edges
6.  Recursive subdivision or fractal (nested rectangles, binary tree, Sierpinski)
7.  Scrolling horizontal or vertical bands / scanline glitch with slicing and offset tearing
8.  Kaleidoscope: one wedge mirrored into N sectors
9.  Cellular-automaton or noise grid that evolves cell by cell
10. Typographic: the WORD ITSELF is the graphic - tiled, repeated, mirrored, warped, or blown up huge and clipped by the frame
11. Branching lightning / L-system growth from an edge
12. Perspective checkerboard floor or warped grid with a moving horizon

=== ANTI-SAMENESS RULES (these matter more than the math) ===
A. DO NOT center everything at (64,32). Uniform centered radial blobs all look identical no matter how clever the equations are. At least half the families must be full-frame, off-center, edge-anchored, or asymmetric.
B. VARY THE POLARITY. Roughly a third of the families must draw black-on-white: fill the image with 255 and draw with 0. On a monochrome panel this is the single largest perceived difference between two frames.
C. VARY THE DENSITY. Some families sparse (scattered points), some dense (large filled masses). Do not make everything a mid-density web of lines.
D. USE DITHERING FOR GRADIENTS. Compute a float intensity per pixel with numpy, then threshold it against an ordered 4x4 Bayer matrix to get 0/255. This yields apparent gradients, glow and shading, which read far better on an OLED than wireframes.
E. PREFER FILLED SHAPES AND LARGE MASSES OVER 1-PIXEL LINES. Single-pixel lines shimmer and look sparse at 128x64.

=== EVOLUTION WITHIN EACH WORD ===
Words last only 0.15 to 1.3 seconds, so each effect must read instantly and must visibly change across its own duration. Compute:
    progress = clamp((current_time - start) / max(end - start, 1e-3), 0.0, 1.0)
Drive the effect with `progress`, not only with `current_time`, so it grows, explodes, collapses or sweeps across the word. Give every word a hard visual ATTACK in its first ~100ms (a flash, a full-frame inversion, or a burst) so the beat of the lyrics is felt.

=== GAPS ===
For `type == "gap"`, run a slow, evolving, cinematic instrumental scene driven by `current_time`. Switch between several gap scenes based on `int(current_time / 4) % N` so a long instrumental break does not sit on one image.

=== TEXT RENDERING (this part already works - keep it exactly) ===
Render the word clearly on top of the background geometry, perfectly centered. DO NOT draw a solid black background box behind the text; it would cover the animation. Instead draw a 1-pixel black outline around the glyphs by drawing the text 8 times at +/-1 pixel offsets in black, then the white text on top. Load a TrueType font ('arial.ttf') and mathematically shrink `font_size` until `textbbox` fits inside 128x64. Never scale a bitmap font. If the background family is white-on-black polarity, invert the text colors so it stays readable.

=== PERFORMANCE (hard requirement) ===
The frame must render in under 15 ms or the display will stutter.
- Cache fonts at module level in a dict keyed by size. NEVER call `ImageFont.truetype()` inside the sizing loop on every frame.
- Precompute numpy coordinate grids (`YY, XX = np.mgrid[0:64, 0:128]`) once at module level.
- Use vectorised numpy for any per-pixel effect. Never write nested Python loops over all 8192 pixels.
- Build per-pixel effects as a numpy array and convert with `Image.fromarray(arr.astype(np.uint8), 'L')`.

DO NOT write a main loop. DO NOT write video generation code. Output ONLY the complete `generated_visuals.py` module.
"""

def get_audio_input():
    root = tk.Tk()
    root.withdraw()
    
    # Ask for YouTube link first via a popup dialog
    yt_url = simpledialog.askstring("Input", "Enter a YouTube URL (or leave blank to select a local file):")
    
    if yt_url and yt_url.strip():
        try:
            import yt_dlp
        except ImportError:
            print("ERROR: yt-dlp is not installed.")
            print("Please run this in your terminal: pip install yt-dlp")
            sys.exit(1)
            
        print(f"\nDownloading audio from YouTube: {yt_url}")
        
        # Configure yt-dlp to download the best audio and convert to MP3
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': '%(title)s.%(ext)s',
            'quiet': False,
            # PROTECTIVE MEASURE: If the user provides a playlist link, only download the first video!
            'noplaylist': True,
            # Fix: yt-dlp's Python API requires this to be a dictionary, not a list
            'js_runtimes': {'node': {}},
            # Force mobile clients to bypass YouTube's strict desktop anti-bot blocks
            'extractor_args': {'youtube': {'player_client': ['android']}}
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(yt_url.strip(), download=True)
            filename = ydl.prepare_filename(info_dict)
            base, _ = os.path.splitext(filename)
            mp3_path = base + ".mp3"
            
            # The download finishes, return the local path to the new mp3
            return mp3_path
    else:
        # Fallback to local file selection if no link is provided
        print("Please select your media file (.mp3, .wav, .mp4, .mkv, etc.)")
        return filedialog.askopenfilename(title="Select Media File", filetypes=[("Media Files", "*.mp3 *.wav *.mp4 *.mkv *.avi *.mov *.m4a *.aac"), ("All Files", "*.*")])

def main():
    try:
        import whisper
    except ImportError:
        print("ERROR: openai-whisper is not installed.")
        print("Please run: pip install -U openai-whisper")
        sys.exit(1)

    print("Welcome to the AI Whisper Timeline Generator!")
    
    audio_path = get_audio_input()
    
    if not audio_path or not os.path.exists(audio_path):
        print("No valid file selected or downloaded. Exiting.")
        return
        
    # Ask the user for the model accuracy level
    model_size = simpledialog.askstring("Accuracy Level", "Enter Whisper model size:\n(tiny, base, small, medium, large)\n\nLarger models are MUCH more accurate for music, but take longer to download and run.", initialvalue="small")
    if not model_size:
        model_size = "small"
    model_size = model_size.strip().lower()

    print(f"\nLoading AI Transcription Model ({model_size})...")
    print("If this is your first time, it might take a moment to download the model.")
    
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    model = whisper.load_model(model_size, device=device)

    print(f"\nTranscribing {os.path.basename(audio_path)}...")
    print("Listening to the audio... (This will take a few minutes depending on your PC speed)")
    
    # word_timestamps=True gives us the exact start/end of every word
    result = model.transcribe(audio_path, word_timestamps=True)
    
    timeline = []
    last_end = 0.0
    
    print("\n--- Transcription Progress ---")
    for segment in result.get("segments", []):
        for word_info in segment.get("words", []):
            start = round(word_info["start"], 3)
            end = round(word_info["end"], 3)
            text = word_info["word"].strip()
            
            # Remove punctuation so it looks clean on the OLED
            import re
            text = re.sub(r'[^\w\s]', '', text)
            
            if not text:
                continue
                
            # If there's a gap of more than 1 second between words, add a GAP event
            gap_duration = start - last_end
            if gap_duration > 1.0: 
                timeline.append({
                    "type": "gap",
                    "start": last_end,
                    "end": start
                })
                
            timeline.append({
                "type": "word",
                "text": text,
                "start": start,
                "end": end
            })
            
            last_end = end
            print(f"[{start:.2f}s - {end:.2f}s] {text}")
            
    # Add a final gap at the end for the outro animation
    timeline.append({
        "type": "gap",
        "start": last_end,
        "end": last_end + 5.0
    })
    
    out_dir = os.path.dirname(audio_path)
    json_path = os.path.join(out_dir, "timeline.json")
    prompt_path = os.path.join(out_dir, "llm_prompt.txt")
    
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(timeline, f, indent=2)
        
    title = os.path.splitext(os.path.basename(audio_path))[0]
    
    prompt_text = PROMPT_TEMPLATE.replace("__SONG_TITLE__", title)
    prompt_text += "\n" + json.dumps(timeline[:15], indent=2) + "\n... (full data is in timeline.json)\n"
    
    with open(prompt_path, "w", encoding='utf-8') as f:
        f.write(prompt_text)
        
    print(f"\n--- SUCCESS ---")
    print(f"Created Perfect Timeline: {json_path}")
    print(f"Created LLM Prompt:       {prompt_path}")

if __name__ == "__main__":
    main()
