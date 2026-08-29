import math
import hashlib
from PIL import Image, ImageDraw, ImageFont

def render_frame(current_time, current_event):
    # Fallback for missing/empty events
    if not current_event:
        current_event = {"type": "gap"}

    # Initialize 128x64 1-bit grayscale image
    img = Image.new('L', (128, 64), color=0)
    draw = ImageDraw.Draw(img)

    event_type = current_event.get("type", "gap")
    text = current_event.get("text", "")

    if event_type == "gap" or not text:
        # ==========================================
        # PROCEDURAL ENGINE: INTENSE MATH-ART (GAPS)
        # ==========================================
        t = current_time
        cx, cy = 64, 32
        points = []
        num_points = 80
        
        # Generate an evolving 3D-style Lissajous curve
        for i in range(num_points):
            u = i / float(num_points) * math.pi * 2
            # Parametric equations that shift dynamically over time
            x = 55 * math.sin(3 * u + t * 1.5) * math.cos(u + t * 0.8)
            y = 30 * math.sin(2 * u - t * 1.2)
            points.append((cx + x, cy + y))
        
        # Connect the points to form a wireframe mesh
        for i in range(num_points):
            p1 = points[i]
            p2 = points[(i + 1) % num_points]
            draw.line([p1, p2], fill=255, width=1)
            
        # Add a dynamic background starfield projection
        for i in range(25):
            sx = (math.sin(t * (i + 1) * 0.1) * 64 + 64) % 128
            sy = (math.cos(t * (i + 2) * 0.1) * 32 + 32) % 64
            draw.point((sx, sy), fill=255)
            
    else:
        # ==========================================
        # PROCEDURAL ENGINE: UNIQUE WORD GEOMETRY
        # ==========================================
        # Generate a stable, unique integer seed based on the word
        h = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)
        
        # Derive mathematical animation parameters from the hash
        num_nodes = (h % 5) + 3           # 3 to 7 geometric nodes
        radius = (h % 15) + 15            # Spacing radius: 15 to 29
        speed = ((h % 100) / 50.0) + 0.5  # Rotation speed: 0.5 to 2.5
        direction = 1 if h % 2 == 0 else -1
        phase_shift = (h % 314) / 100.0   # Unique starting angle offset
        
        cx, cy = 64, 32
        angle = current_time * speed * direction + phase_shift
        
        # Calculate rotating polygon nodes
        poly_points = []
        for i in range(num_nodes):
            theta = angle + (i / float(num_nodes)) * math.pi * 2
            px = cx + radius * math.cos(theta)
            py = cy + radius * math.sin(theta)
            poly_points.append((px, py))
            
        # Draw interlocking geometry between all nodes
        for i in range(num_nodes):
            for j in range(i + 1, num_nodes):
                draw.line([poly_points[i], poly_points[j]], fill=255, width=1)
                
        # Generate particle physics tied to the specific word's length and hash
        num_particles = min(len(text) * 3, 30)
        for i in range(num_particles):
            p_seed = (h * (i + 1)) % 1000
            p_speed = (p_seed % 10) / 5.0 + 0.5
            p_angle = (p_seed % 360) * math.pi / 180.0
            dist = ((current_time * 25 * p_speed) + p_seed) % 80
            
            px = cx + dist * math.cos(p_angle)
            py = cy + dist * math.sin(p_angle)
            if 0 <= px < 128 and 0 <= py < 64:
                draw.point((px, py), fill=255)

        # ==========================================
        # TEXT RENDERING: DYNAMIC SCALING & OUTLINE
        # ==========================================
        font_size = 64
        font = None
        
        try:
            # Shrink font mathematically until textbbox fits within 128x64
            font = ImageFont.truetype("arial.ttf", font_size)
            while font_size > 8:
                bbox = draw.textbbox((0, 0), text, font=font)
                w = bbox[2] - bbox[0]
                h_text = bbox[3] - bbox[1]
                # Max dimensions with a small margin
                if w <= 124 and h_text <= 60:
                    break
                font_size -= 2
                font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            # Safe fallback if TrueType font is missing
            font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h_text = bbox[3] - bbox[1]

        # Calculate exact center coordinates
        x = (128 - w) / 2.0 - bbox[0]
        y = (64 - h_text) / 2.0 - bbox[1]

        # Render 1-pixel Black Outline to separate text from background math-art
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=0)

        # Render White Text Foreground
        draw.text((x, y), text, font=font, fill=255)

    return img