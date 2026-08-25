import cv2
import numpy as np

img = np.zeros((64, 128), dtype=np.uint8)
cv2.putText(img, 'Hello,', (30, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 255, 2)
cv2.putText(img, 'World!', (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 255, 2)

binary = img // 255
pages = binary.reshape(8, 8, 128)
weights = np.array([1, 2, 4, 8, 16, 32, 64, 128], dtype=np.uint8).reshape(1, 8, 1)
packed = np.sum(pages * weights, axis=1, dtype=np.uint8)
raw_bytes = packed.tobytes()

with open('node_code/src/main.cpp', 'r') as f:
    code = f.read()

c_array = ', '.join([f'0x{b:02X}' for b in raw_bytes])
import re
new_code = re.sub(r'const uint8_t splashScreen\[1024\] PROGMEM = \{.*?\};', f'const uint8_t splashScreen[1024] PROGMEM = {{{c_array}}};', code, flags=re.DOTALL)

with open('node_code/src/main.cpp', 'w') as f:
    f.write(new_code)
