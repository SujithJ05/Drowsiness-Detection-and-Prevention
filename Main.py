import cv2
import time
import numpy as np
import traceback
from src import config
from src.services.vision_service import VisionService
from src.services.hardware_service import create_hardware_service
from src.services.alert_service import AlertService
from src.services.data_logger import DataLogger
from src.services.fusion_service import FusionService
from src.services.display_service import DisplayService

def main():
    # 1. Initialize SOTA Services
    vision = VisionService()
    # Use factory to get Real or Mock hardware based on config
    hardware = create_hardware_service()
    logger = DataLogger()
    alerts = AlertService(hardware, logger)
    fusion = FusionService()
    display = DisplayService()
    
    cap = None
    
    try:
        # 2. Connect Hardware
        if not hardware.connect():
            print("WARNING: Hardware connection failed. System will proceed but actuators are disabled.")
        
        # 3. Start Camera
        print(f"Initializing camera at index {config.CAMERA_INDEX}...")
        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not cap.isOpened():
            print(f"CRITICAL ERROR: Could not open camera {config.CAMERA_INDEX}. Check connection.")
            return

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        vision.init_camera(width, height)
        
        print("--- SOTA Driver Monitoring System Initialized ---")
        print("Press 'q' to quit, 'r' to reset alerts.")
        
        # State
        calibration_frames = []
        baseline_pitch = 0.0
        
        while True:
            ret, frame = cap.read()
            if not ret: 
                print("Error reading frame from camera.")
                break
            
            # A. Vision Processing
            results = vision.process_frame(frame)
            landmarks = vision.get_landmarks_array(frame, results)
            
            if landmarks is not None:
                # B. Extract Features
                ear = (vision.calculate_ear(vision.LEFT_EYE, landmarks) + 
                       vision.calculate_ear(vision.RIGHT_EYE, landmarks)) / 2.0
                mar = vision.calculate_mar(vision.MOUTH, landmarks)
                success, pose, rvec, tvec = vision.get_head_pose(landmarks)
                
                # C. Calibration Phase
                if len(calibration_frames) < config.CALIBRATION_FRAMES:
                    if success: calibration_frames.append(pose[0]) # Store Pitch
                    cv2.putText(frame, f"CALIBRATING SENSORS... {len(calibration_frames)}/{config.CALIBRATION_FRAMES}", (10, height//2), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    cv2.imshow("Advanced Driver Monitor", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'): break
                    continue
                elif baseline_pitch == 0.0:
                    baseline_pitch = np.mean(calibration_frames) if calibration_frames else 0.0
                    print(f"Calibration Complete. Baseline Pitch: {baseline_pitch:.2f}")

                # D. Sensor Fusion & Analysis
                current_pitch = pose[0] if success else baseline_pitch
                fatigue_score = fusion.update(ear, mar, current_pitch, baseline_pitch)
                status_text, status_color = fusion.get_status()
                
                # E. Safety Triggers
                is_drowsy = fatigue_score >= config.FUSION_WARNING_THRESHOLD
                alerts.update(is_drowsy, f"Fatigue: {fatigue_score:.2f}")

                # --- RESEARCH LOGGING ---
                if config._CONFIG["logging"]["enabled"]:
                    fusion_metrics = fusion.get_metrics()
                    log_data = {
                        "ear": ear,
                        "mar": mar,
                        "pitch": current_pitch,
                        "yaw": pose[1] if success else 0,
                        "roll": pose[2] if success else 0,
                        "perclos": fusion_metrics["perclos"],
                        "yawn_score": fusion_metrics["yawn_score"],
                        "microsleep_score": fusion_metrics["microsleep_score"],
                        "head_score": fusion_metrics["head_score"],
                        "fusion_score": fatigue_score,
                        "status": status_text,
                        "braking": alerts.braking_activated
                    }
                    logger.log_frame(log_data)
                
                # F. Advanced Visualization (HUD)
                # Draw Face Mesh
                vision.draw_landmarks(frame, landmarks)
                
                # Draw HUD Elements
                frame = display.draw_hud(frame, fatigue_score, status_text, status_color)
                
                # Draw 3D Head Tracking Box
                # Note: This is commented out by default as it can be visually noisy, 
                # uncomment for "Iron Man" demo mode.
                # if success:
                #    display.draw_3d_box(frame, rvec, tvec, vision.camera_matrix, vision.dist_coeffs)

            # G. System Alerts Overlay
            if alerts.braking_activated:
                overlay = frame.copy()
                cv2.rectangle(overlay, (0,0), (width, height), (0,0,255), -1)
                cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
                cv2.putText(frame, "EMERGENCY STOP", (width//2-180, height//2), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 4)

            cv2.imshow("Advanced Driver Monitor", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'): break
            elif key == ord('r'): 
                alerts.reset()
                # Reset fusion state too if needed
                fusion.fatigue_index = 0.0

    except KeyboardInterrupt:
        print("\nUser interrupted execution.")
    except Exception as e:
        print(f"\nUnhandled Exception: {e}")
        traceback.print_exc()
    finally:
        # Cleanup Resources
        print("Shutting down services...")
        if cap and cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()
        if hardware:
            hardware.close()
        print("System Shutdown Complete.")

if __name__ == "__main__":
    main()
