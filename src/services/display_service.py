import cv2
import numpy as np
from collections import deque
from src import config

class DisplayService:
    def __init__(self):
        # Rolling buffer for the graph
        self.graph_data = deque(maxlen=config.GRAPH_BUFFER_SIZE)
        
        # HUD Colors
        self.safe_color = config.HUD_COLOR_SAFE
        self.warn_color = config.HUD_COLOR_WARN
        self.crit_color = config.HUD_COLOR_CRIT

    def draw_hud(self, frame, fatigue_score, status_text, status_color):
        h, w, _ = frame.shape
        
        # 1. Update Graph Data
        self.graph_data.append(fatigue_score)
        
        # 2. Draw Scrolling Graph (Bottom Right)
        self._draw_graph(frame, w, h)
        
        # 3. Draw Status Text (Top Left)
        cv2.putText(frame, "SYSTEM STATUS:", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        cv2.putText(frame, status_text, (220, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        
        # 4. Draw Gauge Bar (Top Right)
        self._draw_gauge(frame, w, fatigue_score)
        
        return frame

    def _draw_graph(self, frame, w, h):
        # Define graph area
        graph_x = w - config.GRAPH_WIDTH - 20
        graph_y = h - config.GRAPH_HEIGHT - 20
        
        # Draw background
        cv2.rectangle(frame, (graph_x, graph_y), (w-20, h-20), (0, 0, 0), -1)
        cv2.rectangle(frame, (graph_x, graph_y), (w-20, h-20), (100, 100, 100), 1)
        
        # Draw grid lines
        cv2.line(frame, (graph_x, graph_y + config.GRAPH_HEIGHT//2), (w-20, graph_y + config.GRAPH_HEIGHT//2), (50, 50, 50), 1)
        
        # Plot points
        if len(self.graph_data) > 1:
            points = []
            for i, val in enumerate(self.graph_data):
                x = graph_x + int((i / config.GRAPH_BUFFER_SIZE) * config.GRAPH_WIDTH)
                y = (h - 20) - int(val * config.GRAPH_HEIGHT)
                points.append((x, y))
            
            # Connect points with lines
            for i in range(1, len(points)):
                color = self.safe_color
                if self.graph_data[i] > config.FUSION_WARNING_THRESHOLD: color = self.warn_color
                if self.graph_data[i] > config.FUSION_CRITICAL_THRESHOLD: color = self.crit_color
                
                cv2.line(frame, points[i-1], points[i], color, 2)

    def _draw_gauge(self, frame, w, val):
        # Draw "Fatigue Level" bar
        bar_x = w - 320
        bar_y = 60
        bar_w = 300
        bar_h = 20
        
        # Background
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 50), -1)
        
        # Fill
        fill_w = int(bar_w * min(val, 1.0))
        color = self.safe_color
        if val > config.FUSION_WARNING_THRESHOLD: color = self.warn_color
        if val > config.FUSION_CRITICAL_THRESHOLD: color = self.crit_color
        
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), color, -1)
        
        # Label
        cv2.putText(frame, f"FATIGUE INDEX: {int(val*100)}%", (bar_x, bar_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    def draw_3d_box(self, frame, rvec, tvec, camera_matrix, dist_coeffs):
        # Project 3D cube points around the face
        axis_len = 100
        points = np.float32([
            [-axis_len, -axis_len, -axis_len], [axis_len, -axis_len, -axis_len],
            [axis_len, axis_len, -axis_len], [-axis_len, axis_len, -axis_len],
            [-axis_len, -axis_len, axis_len], [axis_len, -axis_len, axis_len],
            [axis_len, axis_len, axis_len], [-axis_len, axis_len, axis_len]
        ])
        
        imgpts, _ = cv2.projectPoints(points, rvec, tvec, camera_matrix, dist_coeffs)
        imgpts = np.int32(imgpts).reshape(-1, 2)
        
        # Draw bottom floor
        cv2.drawContours(frame, [imgpts[:4]], -1, (0, 255, 0), 1)
        
        # Draw pillars
        for i in range(4):
            cv2.line(frame, tuple(imgpts[i]), tuple(imgpts[i+4]), (0, 255, 0), 1)
            
        # Draw top roof
        cv2.drawContours(frame, [imgpts[4:]], -1, (0, 255, 0), 1)
        
        return frame
