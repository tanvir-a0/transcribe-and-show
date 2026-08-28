import math
from PIL import Image, ImageDraw, ImageFont

def rotate_3d(x, y, z, pitch, yaw, roll):
    """Applies 3D rotation to a coordinate."""
    # Pitch (x-axis)
    cp, sp = math.cos(pitch), math.sin(pitch)
    y, z = y * cp - z * sp, y * sp + z * cp
    # Yaw (y-axis)
    cy, sy = math.cos(yaw), math.sin(yaw)
    x, z = x * cy + z * sy, -x * sy + z * cy
    # Roll (z-axis)
    cr, sr = math.cos(roll), math.sin(roll)
    x, y = x * cr - y * sr, x * sr + y * cr
    return x, y, z

def project_3d_to_2d(x, y, z, fov=60, viewer_dist=2.5):
    """Projects 3D coordinates to 2D screen space."""
    factor = fov / (viewer_dist + z) if (viewer_dist + z) != 0 else fov
    x_proj = int(64 + x * factor)
    y_proj = int(32 + y * factor)
    return x_proj, y_proj

def draw_star(draw, cx, cy, radius, rotation, fill=255):
    """Draws a procedural 5-pointed star."""
    points = []
    for i in range(10):
        angle = rotation + i * (math.pi / 5)
        r = radius if i % 2 == 0 else radius * 0.4
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, outline=fill)

def render_frame(current_time, current_event):
    # Initialize 128x64 image in Grayscale ('L') mode
    img = Image.new('L', (128, 64), 0)
    draw = ImageDraw.Draw(img)
    
    event_type = current_event.get("type", "gap")
    text = current_event.get("text", "")
    
    # --- BACKGROUND GEOMETRY (Context-Aware) ---
    if event_type == "gap":
        # Intense abstract math-art: Rotating hypercube wireframe & warp tunnel
        
        # Warp Tunnel
        for i in range(40):
            z = (i * 0.5 - current_time * 8.0) % 20.0 + 0.1
            a = i * 0.4 + current_time * 3.0
            tx = math.cos(a) * 15
            ty = math.sin(a) * 15
            px, py = project_3d_to_2d(tx, ty, z, fov=80, viewer_dist=0)
            if 0 <= px < 128 and 0 <= py < 64:
                draw.point((px, py), fill=255)

        # Rotating 3D Cube
        cube_vertices = [
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1),  (1, -1, 1),  (1, 1, 1),  (-1, 1, 1)
        ]
        cube_edges = [
            (0,1), (1,2), (2,3), (3,0),
            (4,5), (5,6), (6,7), (7,4),
            (0,4), (1,5), (2,6), (3,7)
        ]
        pitch = current_time * 0.7
        yaw = current_time * 1.1
        roll = current_time * 1.3
        
        proj_verts = []
        for v in cube_vertices:
            rx, ry, rz = rotate_3d(v[0], v[1], v[2], pitch, yaw, roll)
            proj_verts.append(project_3d_to_2d(rx, ry, rz))
            
        for edge in cube_edges:
            p1 = proj_verts[edge[0]]
            p2 = proj_verts[edge[1]]
            draw.line([p1, p2], fill=255, width=1)
            
    elif event_type == "word":
        lower_text = text.lower()
        
        # 1. Theme: Stars / Counting
        if any(w in lower_text for w in ["star", "stars", "count", "counting"]):
            for i in range(4):
                offset = i * (math.pi / 2)
                cx = 64 + 35 * math.cos(current_time * 2 + offset)
                cy = 32 + 15 * math.sin(current_time * 3 + offset)
                draw_star(draw, cx, cy, radius=8 + 3*math.sin(current_time*5+i), rotation=current_time*(1.5+i*0.5))
                
        # 2. Theme: Money / Dollars / World
        elif any(w in lower_text for w in ["dollar", "dollars", "money", "sold", "world", "pay"]):
            grid_spacing = int(8 + 4 * math.sin(current_time * 2))
            offset_x = int(current_time * 20) % grid_spacing
            offset_y = int(current_time * 15) % grid_spacing
            for x in range(offset_x, 128, grid_spacing):
                draw.line([(x, 0), (x, 64)], fill=255, width=1)
            for y in range(offset_y, 64, grid_spacing):
                draw.line([(0, y), (128, y)], fill=255, width=1)
                
        # 3. Theme: River / Swinging / Vine
        elif any(w in lower_text for w in ["river", "swing", "swinging", "vine", "line"]):
            for i in range(0, 128, 4):
                y1 = 32 + 15 * math.sin(i * 0.05 + current_time * 4) + 8 * math.cos(i * 0.1 + current_time * 2)
                y2 = 32 + 15 * math.sin((i+4) * 0.05 + current_time * 4) + 8 * math.cos((i+4) * 0.1 + current_time * 2)
                draw.line([(i, y1), (i+4, y2)], fill=255, width=1)
                
                # Second overlapping wave
                y3 = 32 + 10 * math.cos(i * 0.04 - current_time * 3)
                y4 = 32 + 10 * math.cos((i+4) * 0.04 - current_time * 3)
                draw.line([(i, y3), (i+4, y4)], fill=255, width=1)
                
        # 4. Theme: Burn / Kill / Alive / Hard
        elif any(w in lower_text for w in ["burn", "kill", "alive", "hard", "fire", "pain"]):
            points = []
            for a in range(0, 360, 10):
                rad = math.radians(a)
                # High frequency jagged noise using trig
                noise = math.sin(a * current_time) * math.cos(a * 2.5 + current_time * 10)
                radius = 20 + 15 * noise
                points.append((64 + radius * math.cos(rad), 32 + radius * math.sin(rad)))
            points.append(points[0])
            draw.line(points, fill=255, width=1)
            
        # 5. Theme: Dreaming / Sleep / Love / Praying
        elif any(w in lower_text for w in ["dream", "sleep", "love", "pray", "faith", "heart", "feel"]):
            # Pulsating concentric mandalas
            for r in range(4, 60, 12):
                pulse = r + 5 * math.sin(current_time * 2 - r * 0.1)
                if pulse > 0:
                    draw.ellipse([64 - pulse, 32 - pulse, 64 + pulse, 32 + pulse], outline=255)
        
        # Default Theme: Complex Lissajous figures
        else:
            prev_x, prev_y = None, None
            for t in range(0, 100):
                t_val = t * 0.1
                A = 40 * math.sin(current_time * 0.5)
                B = 25 * math.cos(current_time * 0.4)
                a_freq, b_freq = 3, 2
                delta = current_time * 2
                
                lx = 64 + A * math.sin(a_freq * t_val + delta)
                ly = 32 + B * math.sin(b_freq * t_val)
                if prev_x is not None:
                    draw.line([(prev_x, prev_y), (lx, ly)], fill=255, width=1)
                prev_x, prev_y = lx, ly

    # --- FOREGROUND TEXT (Perfectly Centered & Scaled) ---
    if event_type == "word" and text:
        font_size = 48
        font = None
        font_name_used = None
        
        # Try finding a standard OS TrueType font
        standard_fonts = ['arial.ttf', 'DejaVuSans.ttf', 'FreeMono.ttf', 'LiberationSans-Regular.ttf', 'tahoma.ttf']
        for fn in standard_fonts:
            try:
                font = ImageFont.truetype(fn, font_size)
                font_name_used = fn
                break
            except IOError:
                continue
                
        # Mathematically shrink to fit inside 128x64 bounds
        if font is not None:
            while font_size > 8:
                bbox = draw.textbbox((0, 0), text, font=font)
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                if w <= 124 and h <= 58:
                    break
                font_size -= 2
                font = ImageFont.truetype(font_name_used, font_size)
        else:
            # Absolute fallback if no TrueType fonts are available on the system
            font = ImageFont.load_default()
            
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        x = (128 - text_w) / 2 - bbox[0]
        y = (64 - text_h) / 2 - bbox[1]
        
        # Draw 1-pixel black outline (DO NOT draw a solid box)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), text, font=font, fill=0)
                
        # Draw crisp white text
        draw.text((x, y), text, font=font, fill=255)

    return img