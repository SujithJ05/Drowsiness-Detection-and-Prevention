import csv
import os
from datetime import datetime
from src import config

class ExperimentLogger:
    def __init__(self):
        self.file_path = config.LOG_FILE
        self._init_file()
        self.frame_count = 0

    def _init_file(self):
        # Create a new unique file for each session if desired, 
        # but for now, we'll append or overwrite based on user preference.
        # Ideally, use a timestamped filename.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{timestamp}.csv"
        self.file_path = os.path.join(config.LOGS_DIR, filename)

        with open(self.file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Timestamp", "Frame", "EAR", "MAR", "Pitch", "Yaw", "Roll",
                "PERCLOS", "YawnScore", "MicroSleepScore", "HeadScore",
                "FusionScore", "Status", "BrakingActive", "Event"
            ])
        print(f"Logging session data to: {self.file_path}")

    def log_frame(self, data):
        """
        Logs a single frame's data for post-hoc analysis.
        data: dict containing all metrics
        """
        self.frame_count += 1
        try:
            with open(self.file_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    self.frame_count,
                    f"{data.get('ear', 0):.4f}",
                    f"{data.get('mar', 0):.4f}",
                    f"{data.get('pitch', 0):.2f}",
                    f"{data.get('yaw', 0):.2f}",
                    f"{data.get('roll', 0):.2f}",
                    f"{data.get('perclos', 0):.4f}",
                    f"{data.get('yawn_score', 0):.2f}",
                    f"{data.get('microsleep_score', 0):.2f}",
                    f"{data.get('head_score', 0):.2f}",
                    f"{data.get('fusion_score', 0):.4f}",
                    data.get('status', 'NORMAL'),
                    data.get('braking', False),
                    data.get('event', '')
                ])
        except Exception as e:
            # Silently fail to avoid crashing the main loop, but print once
            if self.frame_count % 100 == 0:
                print(f"Logging Error: {e}")

    def log_incident(self, incident_type, details=""):
        # Log a special event row
        self.log_frame({
            'event': f"{incident_type}: {details}",
            'status': "INCIDENT"
        })

# Alias for backward compatibility
DataLogger = ExperimentLogger
