from PIL import Image, ImageDraw
import math
import time
import random

# Use the exact parameter matrix from our previous setup
EMOTION_MATRIX = {
    # STATE:             [eye_w, eye_h, eye_y, brow_y, brow_slant, mouth_w, mouth_curve, fx_type,       (R, G, B)]
    "resonance":         [   40,    15,   105,    -35,         15,      80,          25, 0, (0, 255, 150)], 
    "curiosity":         [   40,    55,   100,    -40,         20,      50,           0, 0, (0, 200, 255)], 
    "alignment":         [   40,    55,   100,    -45,          0,      75,          15, 0, (0, 255, 200)], 
    "clarity":           [   45,    65,    95,    -50,          5,      80,          20, 0, (255, 255, 200)],
    "engagement":        [   45,    50,    95,    -40,         10,      95,          35, 0, (0, 255, 100)], 
    "coherence":         [   40,    10,   110,    -30,          0,      70,          15, 0, (150, 255, 200)],
    "confidence":        [   45,    25,   100,    -40,         -5,      85,          10, 0, (0, 150, 255)], 
    "novelty_attraction":[   55,    55,    95,    -50,         15,      90,          40, 0, (255, 200, 0)], 
    "ambiguity":         [   30,    30,   105,    -35,          0,      40,           0, 2, (180, 180, 180)],
    "novelty_neutral":   [   40,    50,    95,    -45,         15,      60,           5, 0, (200, 255, 255)],
    "reorientation":     [   40,    45,   100,    -40,          0,      70,         -10, 3, (200, 150, 255)],
    "latency":           [   40,    12,   115,    -25,         -5,      50,          -5, 0, (100, 150, 200)],
    "equilibrium":       [   40,    50,   100,    -45,          0,      70,           0, 0, (0, 255, 255)], 
    "monitoring":        [   45,    40,    95,    -45,        -20,      75,          -5, 0, (255, 165, 0)], 
    "dissonance":        [   45,    25,    95,    -35,        -25,      90,         -20, 0, (255, 0, 0)],   
    "overload":          [   50,    50,    90,    -55,         25,     100,         -35, 2, (255, 100, 0)], 
    "uncertainty":       [   40,    35,   100,    -35,         15,      65,         -10, 0, (230, 230, 150)],
    "misalignment":      [   35,    45,   105,    -35,        -10,      70,         -15, 0, (255, 120, 120)],
    "incoherence":       [   40,    40,   100,    -40,          0,      50,         -25, 1, (200, 0, 255)], 
    "novelty_aversion":  [   40,    10,   105,    -30,        -20,      65,         -30, 0, (255, 50, 50)],  
    "caution":           [   45,    20,   105,    -35,         -5,      80,           0, 2, (255, 215, 0)], 
    "drift":             [   45,     8,   120,    -20,          5,      55,         -15, 0, (120, 120, 180)],
    "sleep":             [   35,     4,   130,    -15,          0,      40,          -5, 0, (50, 50, 150)]
}

class SynthesizedRobotFace:
    def __init__(self, display_driver):
        self.display = display_driver
        self.frame_count = 0
        
        # --- BLINK STATE MACHINE VARIABLES ---
        self.blink_state = "IDLE"      # Options: IDLE, CLOSING, OPENING
        self.blink_pct = 1.0           # 1.0 = fully open, 0.0 = fully closed
        self.next_blink_time = time.time() + random.uniform(2.5, 6.0)
        self.blink_speed_close = 0.40  # Percentage closure per frame (~2-3 frames)
        self.blink_speed_open = 0.25   # Percentage opening per frame (~4 frames)

    def _process_blink_logic(self):
        """Updates the physical eyelids state independent of the emotion engine."""
        current_time = time.time()

        if self.blink_state == "IDLE":
            # Trigger a blink if the randomized timer has expired
            if current_time >= self.next_blink_time:
                self.blink_state = "CLOSING"

        elif self.blink_state == "CLOSING":
            self.blink_pct -= self.blink_speed_close
            if self.blink_pct <= 0.0:
                self.blink_pct = 0.0
                self.blink_state = "OPENING"

        elif self.blink_state == "OPENING":
            self.blink_pct += self.blink_speed_open
            if self.blink_pct >= 1.0:
                self.blink_pct = 1.0
                self.blink_state = "IDLE"
                # Schedule the next natural random blink interval
                # 10% chance to schedule an immediate double-blink
                if random.random() < 0.10:
                    self.next_blink_time = current_time + random.uniform(0.1, 0.3)
                else:
                    self.next_blink_time = current_time + random.uniform(2.5, 6.0)

    def render_tick(self, active_weights, dominant_emotion):
        """Calculates blended face and injects procedural eye blinking."""
        self.frame_count += 1
        
        # 1. Process our new blink state machine positions
        self._process_blink_logic()
        
        # [ ... Keep the exact same parameter accumulation logic from your current code ... ]
        total_w = sum(active_weights.values())
        if total_w == 0: return
        
        b_eye_w = b_eye_h = b_eye_y = b_brow_y = b_brow_slant = b_mouth_w = b_mouth_curve = 0.0
        b_r = b_g = b_b = 0.0

        for emotion, weight in active_weights.items():
            if emotion not in EMOTION_MATRIX: continue
            params = EMOTION_MATRIX[emotion]
            b_eye_w += params[0] * weight
            b_eye_h += params[1] * weight
            b_eye_y += params[2] * weight
            b_brow_y += params[3] * weight
            b_brow_slant += params[4] * weight
            b_mouth_w += params[5] * weight
            b_mouth_curve += params[6] * weight
            b_r += params[8][0] * weight
            b_g += params[8][1] * weight
            b_b += params[8][2] * weight

        eye_w, eye_h, eye_y = b_eye_w / total_w, b_eye_h / total_w, b_eye_y / total_w
        brow_y, brow_slant  = b_brow_y / total_w, b_brow_slant / total_w
        mouth_w, mouth_curve = b_mouth_w / total_w, b_mouth_curve / total_w
        face_color = (int(b_r / total_w), int(b_g / total_w), int(b_b / total_w))
        fx_type = EMOTION_MATRIX.get(dominant_emotion, [0,0,0,0,0,0,0,0,(0,0,0)])[7]

        # -------------------------------------------------------------
        # INTERCEPT LAYER: Modify eye height based on the blink factor
        # -------------------------------------------------------------
        # We ensure a minimum height of 4 pixels so the eye never disappears entirely,
        # preserving the clean shape on the rectangular screen.
        eye_h = max(4, eye_h * self.blink_pct)
        
        # If your engine enters "sleep" mode, force eyes to stay closed
        if dominant_emotion == "sleep":
            eye_h = 4
            self.blink_state = "IDLE" # Freeze the timer during sleep

        # --- RE-ENGAGE CANVAS GENERATION ---
        img = Image.new("RGB", (320, 240), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Apply shivering modifiers
        shiver_x = shiver_y = 0
        if fx_type == 2: # FX_SHIVER
            shiver_x = int(3 * math.sin(self.frame_count * 1.5))
            shiver_y = int(2 * math.cos(self.frame_count * 1.2))

        # Asymmetric eyebrow modifications
        l_brow_mod = r_brow_mod = brow_slant
        if dominant_emotion in ["monitoring", "curiosity"]:
            mod_intensity = active_weights.get(dominant_emotion, 1.0)
            l_brow_mod += (15 * mod_intensity)
            r_brow_mod -= (10 * mod_intensity)

        # --- DRAW LEFT EYE & BROW ---
        le_cx, le_cy = 90 + shiver_x, eye_y + shiver_y
        if fx_type == 1 and self.blink_pct > 0.3: # Hide dizzy fx when eyes are closed
            r_angle = (self.frame_count * 15) % 360
            draw.arc([le_cx-20, le_cy-20, le_cx+20, le_cy+20], start=r_angle, end=r_angle+270, fill=face_color, width=6)
        else:
            draw.ellipse([le_cx - eye_w/2, le_cy - eye_h/2, le_cx + eye_w/2, le_cy + eye_h/2], fill=face_color)
        draw.line([le_cx - 25, le_cy + brow_y + l_brow_mod, le_cx + 25, le_cy + brow_y - l_brow_mod], fill=face_color, width=6)

        # --- DRAW RIGHT EYE & BROW ---
        re_cx, re_cy = 230 + shiver_x, eye_y + shiver_y
        if fx_type == 1 and self.blink_pct > 0.3:
            r_angle = (self.frame_count * 15 + 180) % 360
            draw.arc([re_cx-20, re_cy-20, re_cx+20, re_cy+20], start=r_angle, end=r_angle+270, fill=face_color, width=6)
        else:
            draw.ellipse([re_cx - eye_w/2, re_cy - eye_h/2, re_cx + eye_w/2, re_cy + eye_h/2], fill=face_color)
        draw.line([re_cx - 25, re_cy + brow_y - r_brow_mod, re_cx + 25, re_cy + brow_y + r_brow_mod], fill=face_color, width=6)

        # --- DRAW MOUTH ---
        m_cx, m_cy = 160 + shiver_x, 180 + shiver_y
        if dominant_emotion == "drift" and active_weights.get("drift", 0.0) > 0.5:
            draw.ellipse([m_cx - 20, m_cy - 10, m_cx + 20, m_cy + 20], fill=face_color)
        elif abs(mouth_curve) < 2:
            draw.line([m_cx - mouth_w/2, m_cy, m_cx + mouth_w/2, m_cy], fill=face_color, width=8)
        elif mouth_curve > 0:
            draw.arc([m_cx - mouth_w/2, m_cy - mouth_curve, m_cx + mouth_w/2, m_cy + mouth_curve], start=0, end=180, fill=face_color, width=8)
        else:
            draw.arc([m_cx - mouth_w/2, m_cy + mouth_curve, m_cx + mouth_w/2, m_cy - mouth_curve], start=180, end=360, fill=face_color, width=8)

        self.display.image(img)

