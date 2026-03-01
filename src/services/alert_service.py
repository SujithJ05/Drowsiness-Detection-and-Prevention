import time
import pygame
import os
from collections import deque
from src import config

class AlertService:
    def __init__(self, hardware_service, logger):
        self.hw = hardware_service
        self.logger = logger
        self.alert_start_time = None
        self.braking_activated = False
        self.is_playing_sound = False
        
        # PERCLOS History (List of (timestamp, is_closed))
        self.eye_history = deque()
        self.fatigue_score = 0.0
        
        # Continuous indicators
        self.micro_sleep_start = None
        self.yawn_start = None
        self.head_nod_start = None

        # Initialize sound
        pygame.mixer.init()
        if os.path.exists(config.SOUND_FILE):
            pygame.mixer.music.load(config.SOUND_FILE)

    def process_telemetry(self, ear, mar, drowsy_head):
        now = time.time()
        
        # 1. Update PERCLOS Window
        is_closed = ear < config.EAR_THRESHOLD
        self.eye_history.append((now, is_closed))
        
        # Remove old data outside window
        while self.eye_history and (now - self.eye_history[0][0] > config.PERCLOS_WINDOW_SIZE):
            self.eye_history.popleft()
            
        # Calculate PERCLOS Score (% of time eyes closed in window)
        if len(self.eye_history) > 0:
            closed_count = sum(1 for _, closed in self.eye_history if closed)
            self.fatigue_score = closed_count / len(self.eye_history)
        
        # 2. Check for Immediate Hazards (Micro-sleep)
        if is_closed:
            if self.micro_sleep_start is None: self.micro_sleep_start = now
            elif now - self.micro_sleep_start > config.MICRO_SLEEP_THRESHOLD:
                return True, "MICRO-SLEEP"
        else:
            self.micro_sleep_start = None

        # 3. Check for Yawning
        if mar > config.MAR_THRESHOLD:
            if self.yawn_start is None: self.yawn_start = now
            elif now - self.yawn_start > config.YAWN_TIME_THRESHOLD:
                return True, "YAWNING"
        else:
            self.yawn_start = None

        # 4. Check Fatigue Score Level
        if self.fatigue_score >= config.FATIGUE_CRITICAL_LEVEL:
            return True, f"FATIGUE CRITICAL ({self.fatigue_score:.2f})"
        elif self.fatigue_score >= config.FATIGUE_WARNING_LEVEL:
            return True, f"FATIGUE WARNING ({self.fatigue_score:.2f})"
            
        return False, "NORMAL"

    def update(self, drowsy, reason):
        now = time.time()
        if drowsy:
            if self.alert_start_time is None:
                self.alert_start_time = now
                self.hw.send_warning()
                self.logger.log_incident("ALERT_TRIGGERED", reason)
            
            self._play_sound()
            
            # Auto-brake check
            elapsed = now - self.alert_start_time
            if elapsed > config.ALERT_TIMEOUT and not self.braking_activated:
                self.trigger_emergency_braking()
        else:
            self._stop_sound()
            if not self.braking_activated:
                self.alert_start_time = None

    def _play_sound(self):
        if not self.is_playing_sound and os.path.exists(config.SOUND_FILE):
            pygame.mixer.music.play(-1)
            self.is_playing_sound = True

    def _stop_sound(self):
        if self.is_playing_sound:
            pygame.mixer.music.stop()
            self.is_playing_sound = False

    def trigger_emergency_braking(self):
        self.hw.apply_brakes()
        self.braking_activated = True
        self.logger.log_incident("EMERGENCY_BRAKING", "Unheeded alert")

    def reset(self):
        self.alert_start_time = None
        self._stop_sound()
        if self.braking_activated:
            self.hw.release_brakes()
            self.braking_activated = False
        self.micro_sleep_start = None
        self.yawn_start = None
        print("System Safe: Driver resumed control.")

    def get_remaining_time(self):
        if self.alert_start_time and not self.braking_activated:
            elapsed = time.time() - self.alert_start_time
            return max(0, config.ALERT_TIMEOUT - elapsed)
        return None
