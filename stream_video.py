import cv2
import serial
import numpy as np
import time
import tkinter as tk
from tkinter import filedialog
import sys

# Configuration
COM_PORT = 'COM8'
BAUD_RATE = 1000000  # High baud rate for fast transfer
FPS_TARGET = 30
FRAME_TIME = 1.0 / FPS_TARGET

skip_request = 0

def setup_serial():
    try:
        ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to {COM_PORT} at {BAUD_RATE} baud.")
        return ser
    except Exception as e:
        print(f"Failed to connect to {COM_PORT}: {e}")
        return None

def select_video_file():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Select Video File",
        filetypes=[("Video Files", "*.mp4 *.mkv *.avi *.mov *.webm"), ("All Files", "*.*")]
    )
    return file_path

def dither_frame(frame):
    # Resize to 128x64
    resized = cv2.resize(frame, (128, 64))
    # Convert to grayscale
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    
    # Fast ordered dithering using a 4x4 Bayer matrix
    bayer = np.array([
        [ 0,  8,  2, 10],
        [12,  4, 14,  6],
        [ 3, 11,  1,  9],
        [15,  7, 13,  5]
    ], dtype=np.uint8) * 16
    
    # Tile the bayer matrix to cover the 128x64 image
    bayer_tiled = np.tile(bayer, (16, 32))
    
    # Threshold the grayscale image against the bayer matrix
    dithered = np.where(gray > bayer_tiled, 255, 0).astype(np.uint8)
    return dithered

def pack_to_ssd1306_format(dithered_frame):
    # The SSD1306 takes data in 8 pages. Each page is 128 columns x 8 vertical pixels (1 byte).
    binary = dithered_frame // 255
    pages = binary.reshape(8, 8, 128)
    
    # Create bit weights for the 8 rows in each page (LSB is top pixel)
    weights = np.array([1, 2, 4, 8, 16, 32, 64, 128], dtype=np.uint8).reshape(1, 8, 1)
    
    # Multiply and sum along the row axis to pack 8 pixels into 1 byte
    packed = np.sum(pages * weights, axis=1, dtype=np.uint8)
    return packed.tobytes()

def mouse_callback(event, x, y, flags, param):
    global skip_request
    if event == cv2.EVENT_LBUTTONDOWN:
        # Check if click is in the buttons bar area (y >= 516) 
        # (256 for original + 4 for separator + 256 for OLED = 516)
        if y >= 516:
            if 50 <= x <= 150:
                skip_request = -10
            elif 362 <= x <= 462:
                skip_request = 10

def draw_buttons_bar():
    bar = np.zeros((50, 512, 3), dtype=np.uint8)
    
    # Draw "<< 10s" button
    cv2.rectangle(bar, (50, 10), (150, 40), (100, 100, 100), -1)
    cv2.putText(bar, "<< 10s", (65, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # Draw "10s >>" button
    cv2.rectangle(bar, (362, 10), (462, 40), (100, 100, 100), -1)
    cv2.putText(bar, "10s >>", (377, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    return bar

def main():
    global skip_request
    print("Please select a video file...")
    video_path = select_video_file()
    if not video_path:
        print("No file selected. Exiting.")
        return

    print(f"Selected video: {video_path}")
    
    ser = setup_serial()
    if not ser:
        print("Please check if the COM port is correct and the ESP32 is plugged in.")
        return
        
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error opening video.")
        return
        
    window_name = "ESP32 OLED Streamer (Press Q to exit)"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, mouse_callback)
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0: fps = 30.0
    
    cv2.createTrackbar("Seek", window_name, 0, total_frames, lambda x: None)
        
    print("Waiting for ESP32 to initialize and send Ready signal...")
    ser.timeout = 5.0 
    ready = ser.read(1)
    if ready == b'K':
        print("ESP32 is ready! Starting stream.")
    else:
        print("Warning: Did not receive Ready signal from ESP32. Attempting to stream anyway...")
    
    ser.timeout = 2.0
    last_set_trackbar_pos = 0
    buttons_bar = draw_buttons_bar()
    
    while True:
        start_time = time.perf_counter()
        
        current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        trackbar_pos = cv2.getTrackbarPos("Seek", window_name)
        
        # Handle trackbar drag or button click
        if skip_request != 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(total_frames - 1, current_frame + int(fps * skip_request))))
            skip_request = 0
            current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        elif abs(trackbar_pos - last_set_trackbar_pos) > 5:
            cap.set(cv2.CAP_PROP_POS_FRAMES, trackbar_pos)
            current_frame = trackbar_pos
            
        cv2.setTrackbarPos("Seek", window_name, current_frame)
        last_set_trackbar_pos = current_frame
            
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
            
        dithered = dither_frame(frame)
        payload = pack_to_ssd1306_format(dithered)
        
        header = bytes([0xAA, 0x55])
        ser.write(header + payload)
        
        ack = ser.read(1)
        if ack != b'K':
            print("Warning: Missed ACK from ESP32. Re-syncing...")
            ser.reset_input_buffer()
        
        elapsed = time.perf_counter() - start_time
        sleep_time = FRAME_TIME - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
            
        # UI Rendering
        original_preview = cv2.resize(frame, (512, 256))
        
        # Convert dithered image (128x64) back to BGR for display and scale to 512x256
        oled_preview = cv2.cvtColor(dithered, cv2.COLOR_GRAY2BGR)
        oled_preview = cv2.resize(oled_preview, (512, 256), interpolation=cv2.INTER_NEAREST)
        
        # Add a small separator bar between previews
        separator = np.zeros((4, 512, 3), dtype=np.uint8)
        separator[:] = (200, 200, 200) # Light grey separator
        
        # Stack vertically: Original -> Separator -> OLED -> Buttons
        unified_ui = np.vstack([original_preview, separator, oled_preview, buttons_bar])
        
        cv2.imshow(window_name, unified_ui)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('d'): 
            skip_request = 10
        elif key == ord('a'): 
            skip_request = -10

    cap.release()
    ser.close()
    cv2.destroyAllWindows()
    print("Playback stopped.")

if __name__ == "__main__":
    main()
