import serial
import numpy as np
import time
import tkinter as tk
from tkinter import filedialog
import cv2
import re
from PIL import Image, ImageDraw, ImageFont
import os

# Configuration
COM_PORT = 'COM8'
BAUD_RATE = 1000000

def setup_serial():
    try:
        ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to {COM_PORT} at {BAUD_RATE} baud.")
        return ser
    except Exception as e:
        print(f"Failed to connect to {COM_PORT}: {e}")
        return None

def select_file(title, filetypes):
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    return file_path

def parse_lrc(lrc_path):
    lines = []
    # format: [mm:ss.xx] lyric
    pattern = re.compile(r'\[(\d+):(\d+\.\d+)\](.*)')
    with open(lrc_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                text = match.group(3).strip()
                time_in_sec = minutes * 60 + seconds
                lines.append((time_in_sec, text))
    # sort by time just in case
    lines.sort(key=lambda x: x[0])
    return lines

def estimate_word_timings(lrc_lines):
    words_timeline = []
    
    for i in range(len(lrc_lines)):
        start_time, text = lrc_lines[i]
        
        # Calculate duration of this line
        if i < len(lrc_lines) - 1:
            end_time = lrc_lines[i+1][0]
        else:
            end_time = start_time + 5.0 # default 5 seconds for the last line
            
        line_duration = end_time - start_time
        
        # Split into words
        words = text.split()
        if not words:
            continue
            
        # Distribute time based on word length + 1 space
        total_chars = sum(len(w) + 1 for w in words)
        if total_chars == 0:
            total_chars = 1
            
        current_time = start_time
        for word in words:
            word_duration = ((len(word) + 1) / total_chars) * line_duration
            words_timeline.append({
                'word': word,
                'start': current_time,
                'end': current_time + word_duration
            })
            current_time += word_duration
            
    return words_timeline

def render_word_to_image(word):
    # Create a blank 128x64 image (black background)
    img = Image.new('L', (128, 64), color=0)
    draw = ImageDraw.Draw(img)
    
    # Scale font down until it fits the screen
    try:
        font_path = "arial.ttf"
        font_size = 60
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        # Fallback if arial is not found
        font = ImageFont.load_default()
        font_size = 10
        
    if isinstance(font, ImageFont.FreeTypeFont):
        while font_size > 8:
            bbox = draw.textbbox((0, 0), word, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if w <= 124 and h <= 60: # Leave some margin (128x64 max)
                break
            font_size -= 2
            font = ImageFont.truetype(font_path, font_size)
            
    # Calculate centered position
    bbox = draw.textbbox((0, 0), word, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (128 - w) / 2
    
    # PIL's textbbox can sometimes be slightly off vertically due to ascenders/descenders. 
    # Center mathematically based on the box.
    y = (64 - h) / 2 - bbox[1] 
    
    # Draw text in white
    draw.text((x, y), word, fill=255, font=font)
    
    # Convert to numpy array
    return np.array(img)

def pack_to_ssd1306_format(binary_frame):
    # binary_frame is 128x64 array of 0s and 255s
    binary = binary_frame // 255
    pages = binary.reshape(8, 8, 128)
    
    # Create bit weights for the 8 rows in each page (LSB is top pixel)
    weights = np.array([1, 2, 4, 8, 16, 32, 64, 128], dtype=np.uint8).reshape(1, 8, 1)
    
    # Multiply and sum along the row axis to pack 8 pixels into 1 byte
    packed = np.sum(pages * weights, axis=1, dtype=np.uint8)
    return packed.tobytes()

def get_current_word(words_timeline, current_time):
    for item in words_timeline:
        if item['start'] <= current_time <= item['end']:
            return item['word']
    return "" # No word to display right now (e.g. between lines)

def main():
    print("Please select the lyrics file (.lrc)...")
    lrc_path = select_file("Select Lyrics File", [("LRC Files", "*.lrc"), ("All Files", "*.*")])
    if not lrc_path:
        print("No LRC file selected. Exiting.")
        return

    print(f"Loading LRC: {lrc_path}")

    lrc_lines = parse_lrc(lrc_path)
    words_timeline = estimate_word_timings(lrc_lines)
    end_time_total = words_timeline[-1]['end'] if words_timeline else 0

    ser = setup_serial()
    if not ser:
        print("Please check if the COM port is correct and the ESP32 is plugged in.")
        return
        
    window_name = "ESP32 Lyrics Streamer (Press Q to exit)"
    cv2.namedWindow(window_name)

    print("Waiting for ESP32 to initialize and send Ready signal...")
    ser.timeout = 5.0 
    ready = ser.read(1)
    if ready == b'K':
        print("ESP32 is ready! Starting stream.")
    else:
        print("Warning: Did not receive Ready signal from ESP32. Attempting to stream anyway...")
    ser.timeout = 2.0

    print("Starting silent lyrics playback...")
    start_time_real = time.time()
    current_displayed_word = None

    while True:
        # Simulate playback time using the built-in clock
        current_time = time.time() - start_time_real
        
        if current_time > end_time_total + 1.0:
            print("Finished lyrics playback.")
            break
        
        word = get_current_word(words_timeline, current_time)
        
        # Only render and send if the word has changed
        if word != current_displayed_word:
            frame = render_word_to_image(word)
            payload = pack_to_ssd1306_format(frame)
            
            header = bytes([0xAA, 0x55])
            ser.write(header + payload)
            
            ack = ser.read(1)
            if ack != b'K':
                print("Warning: Missed ACK from ESP32. Re-syncing...")
                ser.reset_input_buffer()
                
            current_displayed_word = word
            
            # Desktop Preview
            preview = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            preview = cv2.resize(preview, (512, 256), interpolation=cv2.INTER_NEAREST)
            cv2.imshow(window_name, preview)
            
        key = cv2.waitKey(10) & 0xFF
        if key == ord('q'):
            break

    ser.close()
    cv2.destroyAllWindows()
    print("Playback stopped.")

if __name__ == "__main__":
    main()
