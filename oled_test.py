import cv2
import serial
import numpy as np
import time

# Configuration
COM_PORT = 'COM8'
BAUD_RATE = 1000000

def setup_serial():
    try:
        ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to {COM_PORT} at {BAUD_RATE} baud.")
        return ser
    except Exception as e:
        print(f"Failed to connect: {e}")
        return None

def pack_to_ssd1306_format(binary_frame):
    # Reshape into 8 pages of 8 rows
    pages = binary_frame.reshape(8, 8, 128)
    # Bit weights
    weights = np.array([1, 2, 4, 8, 16, 32, 64, 128], dtype=np.uint8).reshape(1, 8, 1)
    # Pack to bytes
    packed = np.sum(pages * weights, axis=1, dtype=np.uint8)
    return packed.tobytes()

def main():
    ser = setup_serial()
    if not ser: 
        return
        
    print("Waiting for ESP32 to initialize...")
    time.sleep(2)

    print("Sending slow test animation (a moving square).")
    print("If this works perfectly, the issue is USB serial buffer overflow from high framerates.")
    
    x_pos = 0
    
    while True:
        # 1. Create a pure black frame
        frame = np.zeros((64, 128), dtype=np.uint8)
        
        # 2. Draw a white square that moves left to right
        frame[20:44, x_pos:x_pos+24] = 1
        
        # 3. Pack and send
        payload = pack_to_ssd1306_format(frame)
        header = bytes([0xAA, 0x55])
        ser.write(header + payload)
        
        # 4. Display on desktop
        display_frame = frame * 255
        cv2.imshow("Test Pattern (Press Q to quit)", display_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
        # Move the square
        x_pos += 4
        if x_pos > 100:
            x_pos = 0
            
        # VERY SLOW FRAMERATE (2 FPS)
        # We wait 0.5 seconds between frames to give the ESP32 plenty of time to catch up
        time.sleep(0.5)

    ser.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
