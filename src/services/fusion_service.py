import time
from collections import deque
import numpy as np
from src import config

class FusionService:
    def __init__(self):
        # Rolling Windows for Temporal Analysis
        self.ear_history = deque(maxlen=int(config.PERCLOS_WINDOW_SIZE * 30)) # 30 FPS approx
        self.mar_history = deque(maxlen=int(config.PERCLOS_WINDOW_SIZE * 30))
        self.pitch_history = deque(maxlen=int(config.PERCLOS_WINDOW_SIZE * 30))
        
        # Continuous Fatigue Score (0.0 to 1.0)
        self.fatigue_index = 0.0
        
        # State Tracking
        self.is_microsleeping = False
        self.microsleep_start = None
        
        self.is_yawning = False
        self.yawn_start = None

        # Store last calculated metrics for logging
        self.last_metrics = {
            "perclos": 0.0,
            "yawn_score": 0.0,
            "head_score": 0.0,
            "microsleep_score": 0.0,
            "raw_score": 0.0
        }

    def update(self, ear, mar, pitch, baseline_pitch):
        now = time.time()
        
        # 1. Update History Buffers
        self.ear_history.append(ear)
        self.mar_history.append(mar)
        self.pitch_history.append(pitch)
        
        # 2. Calculate PERCLOS (Percentage of Eyelid Closure)
        # Count frames where EAR < Threshold
        closed_frames = sum(1 for e in self.ear_history if e < config.EAR_THRESHOLD)
        perclos_score = closed_frames / len(self.ear_history) if len(self.ear_history) > 0 else 0
        
        # 3. Calculate Yawn Frequency/Duration
        if mar > config.MAR_THRESHOLD:
            if self.yawn_start is None: self.yawn_start = now
            yawn_duration = now - self.yawn_start
        else:
            self.yawn_start = None
            yawn_duration = 0
            
        # Normalize Yawn Score (0.0 to 1.0 based on duration)
        yawn_score = min(yawn_duration / config.YAWN_TIME_THRESHOLD, 1.0)
        
        # 4. Calculate Head Droop Score
        rel_pitch = pitch - baseline_pitch
        if rel_pitch < config.DROWSY_PITCH_THRESHOLD: # Looking down
            head_score = 1.0
        else:
            head_score = 0.0
            
        # 5. Microsleep Detection (Immediate Hazard)
        if ear < config.EAR_THRESHOLD:
            if self.microsleep_start is None: self.microsleep_start = now
            ms_duration = now - self.microsleep_start
        else:
            self.microsleep_start = None
            ms_duration = 0
            
        ms_score = min(ms_duration / config.MICRO_SLEEP_THRESHOLD, 1.0)
        
        # --- FUSION ALGORITHM ---
        # Weighted Sum of all factors
        raw_score = (
            (perclos_score * config.W_PERCLOS) +
            (yawn_score * config.W_MOUTH) +
            (head_score * config.W_HEAD) +
            (ms_score * config.W_MICROSLEEP)
        )
        
        # Smooth the output (Low-pass filter) to prevent jittery graph
        self.fatigue_index = (self.fatigue_index * 0.8) + (raw_score * 0.2)
        
        # Cap at 1.0
        self.fatigue_index = min(self.fatigue_index, 1.0)
        
        # Store metrics for logging/analysis
        self.last_metrics = {
            "perclos": perclos_score,
            "yawn_score": yawn_score,
            "head_score": head_score,
            "microsleep_score": ms_score,
            "raw_score": raw_score
        }

        return self.fatigue_index

    def get_metrics(self):
        """Returns the dictionary of the most recent calculation components."""
        return self.last_metrics

    def get_status(self):
        if self.fatigue_index >= config.FUSION_CRITICAL_THRESHOLD:
            return "CRITICAL", config.HUD_COLOR_CRIT
        elif self.fatigue_index >= config.FUSION_WARNING_THRESHOLD:
            return "WARNING", config.HUD_COLOR_WARN
        else:
            return "NORMAL", config.HUD_COLOR_SAFE
