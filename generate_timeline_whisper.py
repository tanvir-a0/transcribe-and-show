import tkinter as tk
from tkinter import filedialog, simpledialog
import json
import os
import sys

# Fix for the OpenMP duplicate library error (common in Conda environments with PyTorch + OpenCV)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

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
    
    prompt_text = f"""You are an expert creative generative artist and Python developer. 
I am building a live procedural music visualizer for a monochrome OLED display (128x64 pixels, 1-bit color).
The visualizer is specifically for the song '{title}'.

I have a `timeline.json` mapping lyrics and gaps to exact millisecond timestamps.

YOUR TASK:
Write a Python file named `generated_visuals.py`. It MUST contain EXACTLY this function signature:
`def render_frame(current_time, current_event):`

- `current_time`: A float representing seconds elapsed.
- `current_event`: A dictionary from the timeline (e.g., `{{"type": "word", "text": "Hello"}}` or `{{"type": "gap"}}`). IMPORTANT: This may be `None` or an empty dict `{{}}`, so always use `if not current_event: current_event = {{"type": "gap"}}` to be safe!
- The function MUST return a `PIL.Image` object in 'L' mode (grayscale), strictly 128x64 pixels. Colors can only be 0 (black) and 255 (white).

COMPLEXITY REQUIREMENTS:
I do not want basic shapes and I DO NOT want repetitive animations!
1. DO NOT hardcode a few generic `if/elif` blocks for specific words (e.g. `if "time" in text:`). That results in boring, repetitive graphics for the rest of the song.
2. Instead, build a HIGHLY DYNAMIC PROCEDURAL ENGINE. Use properties of the current text (like `len(text)`, or `hash(text) % 20`, or its ASCII values) to mathematically alter the animation parameters! For example, use the word's hash to randomly change the rotation speed, the number of geometric nodes, the fractal depth, or the particle physics gravity. This guarantees that EVERY SINGLE WORD in the entire song gets a completely unique, non-repetitive graphical variation.
3. For gaps (when no word is sung), generate intense abstract geometric math-art (e.g., 3D wireframe projections, starfields, or Lissajous curves) that heavily evolves over `current_time`.
4. The text must always be rendered clearly on top of the background geometry, perfectly centered. CRITICAL: DO NOT draw a solid black background box behind the text, as it will cover the background animations! Instead, draw a 1-pixel black outline around the letters for contrast, then draw the white text. Load a TrueType font (e.g., 'arial.ttf') and mathematically shrink `font_size` so `textbbox` fits within 128x64. Do not scale bitmap images!

DO NOT write a loop. DO NOT write video generation code. ONLY provide the `generated_visuals.py` module with the `render_frame` function.
"""
    prompt_text += "\n" + json.dumps(timeline[:15], indent=2) + "\n... (full data is in timeline.json)\n"
    
    with open(prompt_path, "w", encoding='utf-8') as f:
        f.write(prompt_text)
        
    print(f"\n--- SUCCESS ---")
    print(f"Created Perfect Timeline: {json_path}")
    print(f"Created LLM Prompt:       {prompt_path}")

if __name__ == "__main__":
    main()
