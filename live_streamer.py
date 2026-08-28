import serial
import numpy as np
import time
import json
import cv2
import importlib
import sys
import tkinter as tk
from tkinter import filedialog

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

def pack_to_ssd1306_format(binary_frame):
    binary = binary_frame // 255
    pages = binary.reshape(8, 8, 128)
    weights = np.array([1, 2, 4, 8, 16, 32, 64, 128], dtype=np.uint8).reshape(1, 8, 1)
    packed = np.sum(pages * weights, axis=1, dtype=np.uint8)
    return packed.tobytes()

def get_current_event(timeline, current_time):
    for event in timeline:
        if event['start'] <= current_time <= event['end']:
            return event
    return None

def main():
    print("Loading timeline.json...")
    try:
        with open("timeline.json", "r") as f:
            timeline = json.load(f)
    except FileNotFoundError:
        print("Could not find timeline.json! Run generate_timeline_and_prompt.py first.")
        return
        
    end_time_total = timeline[-1]['end'] if timeline else 0

    print("Importing LLM generated visuals module...")
    try:
        import generated_visuals
        importlib.reload(generated_visuals) # Allow hot-reloading if modified
    except ImportError:
        print("ERROR: Could not import generated_visuals.py!")
        print("Please ask the LLM to generate it, save it in this folder, and try again.")
        return

    ser = setup_serial()
    if not ser:
        print("Please check if the COM port is correct and the ESP32 is plugged in.")
        return
        
    window_name = "ESP32 Live Procedural Streamer (Press Q to exit)"
    cv2.namedWindow(window_name)

    print("Waiting for ESP32 to initialize and send Ready signal...")
    ser.timeout = 5.0 
    ready = ser.read(1)
    if ready == b'K':
        print("ESP32 is ready!")
    ser.timeout = 2.0

    print("\nREADY TO START!")
    print("Press ENTER in this console when you hit play on your music...")
    input()
    
    start_time_real = time.time()
    
    while True:
        current_time = time.time() - start_time_real
        
        if current_time > end_time_total + 1.0:
            print("Timeline finished.")
            break
            
        current_event = get_current_event(timeline, current_time)
        if current_event is None:
            current_event = {"type": "gap"}
            
        # Call the LLM's complex procedural function
        try:
            pil_image = generated_visuals.render_frame(current_time, current_event)
            frame = np.array(pil_image)
            
            # Send to ESP32
            payload = pack_to_ssd1306_format(frame)
            header = bytes([0xAA, 0x55])
            ser.write(header + payload)
            
            ack = ser.read(1)
            if ack != b'K':
                ser.reset_input_buffer()
                
            # Desktop Preview
            preview = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            preview = cv2.resize(preview, (512, 256), interpolation=cv2.INTER_NEAREST)
            cv2.imshow(window_name, preview)
            
        except Exception as e:
            print(f"Error in LLM graphics code: {e}")
            break
            
        key = cv2.waitKey(10) & 0xFF
        if key == ord('q'):
            break

    ser.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
