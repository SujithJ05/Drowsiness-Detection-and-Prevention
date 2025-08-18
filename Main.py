import cv2
import numpy as np
import pygame
import time
import os
import dlib
import serial.tools.list_ports  # Force correct import
import serial  # For Arduino communication
from scipy.spatial import distance as dist

def connect_to_arduino(port="COM7", baud_rate=9600, timeout=3):
    """
    Detailed Arduino connection function with extensive debugging
    """
    try:
        # Print detailed port information
        available_ports = list(serial.tools.list_ports.comports())
        print("Detailed COM Ports:")
        for p in available_ports:
            print(f"  Port: {p.device}")
            print(f"    Description: {p.description}")
            print(f"    Manufacturer: {p.manufacturer}")
            print(f"    Product: {p.product}")
            print(f"    Serial Number: {p.serial_number}")
            print("-" * 40)
        
        print(f"\nAttempting to connect to Arduino on {port}...")
        
        # More robust serial connection
        ser = serial.Serial(
            port=port, 
            baudrate=baud_rate, 
            timeout=timeout,
            write_timeout=timeout,
            inter_byte_timeout=timeout
        )
        
        # Give Arduino time to reset
        print("Waiting for Arduino to initialize...")
        time.sleep(2)
        
        # Flush any existing buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Send multiple test messages
        test_messages = [b"HELLO\n", b"STATUS\n", b"TEST\n"]
        for msg in test_messages:
            try:
                print(f"Sending test message: {msg.decode().strip()}")
                ser.write(msg)
                
                # Wait for response
                time.sleep(0.5)
                
                # Read and print response
                if ser.in_waiting > 0:
                    response = ser.readline().decode('utf-8', errors='ignore').strip()
                    print(f"Arduino response: {response}")
                else:
                    print("No immediate response received")
            
            except Exception as send_error:
                print(f"Error sending message: {send_error}")
        
        # Final status
        print(f"Successfully opened serial connection on {port}")
        return port, ser, True
    
    except serial.SerialException as e:
        print(f"Serial Connection Error: {e}")
        print("Possible reasons:")
        print("1. Port already in use")
        print("2. Device not connected")
        print("3. Incorrect port")
        print("4. Driver issues")
        return None, None, False
    
    except Exception as e:
        print(f"Unexpected connection error: {e}")
        return None, None, False

# Run connection test
if __name__ == "__main__":    connect_to_arduino()

# Global variables for Arduino connection
ARDUINO_PORT = None
arduino_serial = None
arduino_connected = False

# Try to establish connection at the start
ARDUINO_PORT, arduino_serial, arduino_connected = connect_to_arduino()

# Auto-braking system parameters
ALERT_TIMEOUT = 5.0  # Seconds after alert before auto-braking activates
alert_start_time = None  # Time when alert started
braking_activated = False  # Tracks if emergency braking is currently active
driver_responded = False  # Tracks if driver responded to the alert

# Initialize pygame for alert sound
pygame.mixer.init()

# Path to the sound file - using a variable to make it easier to troubleshoot
SOUND_FILE = r"C:\Users\sujit\OneDrive\Desktop\Project E11\beep-beep-beep-beep-80262 (2).mp3"
# Check if the sound file exists
if not os.path.exists(SOUND_FILE):
    print(f"WARNING: Sound file not found: {SOUND_FILE}")
    print("Using a fallback sound")
    # Create a simple beep using pygame as fallback
    pygame.mixer.Sound(buffer=pygame.sndarray.make_sound(np.array([4000] * 44100, dtype=np.int16)))
    SOUND_FILE = None

# Load dlib's face detector and facial landmark predictor
predictor_path = "shape_predictor_68_face_landmarks.dat"
if not os.path.exists(predictor_path):
    print(f"ERROR: Landmark predictor file not found: {predictor_path}")
    predictor_path = input("Enter the full path to the landmark predictor file: ")

# Initialize dlib's face detector and facial landmark predictor
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(predictor_path)

# Thresholds for drowsiness detection
EAR_THRESHOLD = 0.25     # Eye Aspect Ratio threshold - increased from 0.2
MAR_THRESHOLD = 14.0    # Mouth Aspect Ratio threshold - adjusted
TIME_THRESHOLD = 2.0      # Time threshold in seconds

# UPDATED head tilt thresholds - more permissive to reduce false positives
HEAD_PITCH_THRESHOLD = 30.0  # Forward/backward tilt threshold (in degrees) - increased
HEAD_YAW_THRESHOLD = 45.0    # Left/right tilt threshold (in degrees) - increased
HEAD_ROLL_THRESHOLD = 30.0   # Sideways tilt threshold (in degrees) - increased

# IMPROVED: Specific thresholds for drowsiness-related head movements
# Downward head tilt (nodding) is the primary indicator of drowsiness
DROWSY_PITCH_THRESHOLD = -20.0  # Negative pitch means head is tilting down
DROWSY_HEAD_DURATION = 1.5  # Require head tilt to persist longer to trigger alert

# Flags and timers
beep_playing = False
eye_close_start_time = None
yawn_start_time = None
head_tilt_start_time = None
head_poses = []  # To track head pose angles
last_frame_time = time.time()  # For FPS calculation
head_tilt_baseline = None  # Store user's natural head position as baseline
calibration_frames = 0  # Count frames for calibration

# Initialize reference 3D model points for head pose estimation
# The 3D model points correspond to specific facial landmarks:
# Nose tip, Chin, Left eye left corner, Right eye right corner, Left mouth corner, Right mouth corner
model_points = np.array([
    (0.0, 0.0, 0.0),             # Nose tip (point 30)
    (0.0, -330.0, -65.0),        # Chin (point 8)
    (-225.0, 170.0, -135.0),     # Left eye left corner (point 36)
    (225.0, 170.0, -135.0),      # Right eye right corner (point 45)
    (-150.0, -150.0, -125.0),    # Left mouth corner (point 48)
    (150.0, -150.0, -125.0)      # Right mouth corner (point 54)
], dtype=np.float64)

# Camera matrix estimation (will be refined after first frame)
camera_matrix = None
dist_coeffs = np.zeros((4, 1))  # Assuming no lens distortion

try:
    # Start video capture with error handling
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        cap = cv2.VideoCapture(1)  # Try alternative camera index
        if not cap.isOpened():
            print("Error: Could not open any camera. Please check your webcam connection.")
            exit(1)
except Exception as e:
    print(f"Error initializing camera: {e}")
    exit(1)

# Get camera resolution
frame_width = int(cap.get(3))
frame_height = int(cap.get(4))

# Estimate camera matrix based on frame size
if camera_matrix is None:
    focal_length = frame_width
    center = (frame_width / 2, frame_height / 2)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype=np.float64)

print(f"Camera initialized with resolution: {frame_width}x{frame_height}")
print("Press 'q' to quit the application")
print("Press 'r' to reset/respond to alerts")
print("Calibrating head position - please look straight at the camera...")

def calculate_ear(eye_points, facial_landmarks):
    """Calculate Eye Aspect Ratio (EAR) using the standard formula"""
    try:
        # Get the vertical distances between landmarks
        A = dist.euclidean(
            facial_landmarks[eye_points[1]], 
            facial_landmarks[eye_points[5]]
        )
        B = dist.euclidean(
            facial_landmarks[eye_points[2]], 
            facial_landmarks[eye_points[4]]
        )
        
        # Get the horizontal distance
        C = dist.euclidean(
            facial_landmarks[eye_points[0]], 
            facial_landmarks[eye_points[3]]
        )
        
        # Prevent division by zero
        if C == 0:
            return 1.0
            
        # Calculate EAR
        ear = (A + B) / (2.0 * C)
        return ear
    except Exception as e:
        print(f"Error calculating EAR: {e}")
        return 1.0  # Return a default value on error

def calculate_mar(mouth_points, facial_landmarks):
    """Calculate Mouth Aspect Ratio (MAR) for yawn detection"""
    try:
        # Use inner mouth landmarks for better yawn detection
        # Vertical distances (use multiple points for robustness)
        A = dist.euclidean(
            facial_landmarks[mouth_points[2]], 
            facial_landmarks[mouth_points[6]]
        )
        B = dist.euclidean(
            facial_landmarks[mouth_points[3]], 
            facial_landmarks[mouth_points[7]]
        )
        
        # Horizontal distance
        C = dist.euclidean(
            facial_landmarks[mouth_points[0]], 
            facial_landmarks[mouth_points[4]]
        )
        
        # Prevent division by zero
        if C == 0:
            return 0.0
            
        # Calculate MAR with appropriate scaling
        mar = ((A + B) / C) * 15
        return mar
    except Exception as e:
        print(f"Error calculating MAR: {e}")
        return 0.0  # Return a default value on error

def detect_head_pose(landmarks, frame):
    """
    Estimate head pose using facial landmarks and solvePnP
    Returns: (success, rotation_angles, rotation_vector, translation_vector)
    rotation_angles: (pitch, yaw, roll) in degrees
    """
    try:
        # Get specific facial landmarks for head pose estimation
        image_points = np.array([
            (landmarks.part(30).x, landmarks.part(30).y),  # Nose tip
            (landmarks.part(8).x, landmarks.part(8).y),    # Chin
            (landmarks.part(36).x, landmarks.part(36).y),  # Left eye left corner
            (landmarks.part(45).x, landmarks.part(45).y),  # Right eye right corner
            (landmarks.part(48).x, landmarks.part(48).y),  # Left mouth corner
            (landmarks.part(54).x, landmarks.part(54).y)   # Right mouth corner
        ], dtype="double")
        
        # Solve for pose
        success, rotation_vector, translation_vector = cv2.solvePnP(
            model_points, image_points, camera_matrix, dist_coeffs, 
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        
        if not success:
            return False, (0, 0, 0), None, None
            
        # Convert rotation vector to rotation matrix
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        
        # Get Euler angles (pitch, yaw, roll) in degrees
        # Decompose rotation matrix to get Euler angles
        pitch, yaw, roll = rotation_to_euler_angles(rotation_matrix)
        
        return True, (pitch, yaw, roll), rotation_vector, translation_vector
        
    except Exception as e:
        print(f"Error estimating head pose: {e}")
        return False, (0, 0, 0), None, None

def rotation_to_euler_angles(R):
    """
    Convert rotation matrix to Euler angles (pitch, yaw, roll) in degrees
    """
    try:
        # Checking if rotation matrix is valid
        sy = np.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
        
        if sy > 1e-6:  # Not singular case
            pitch = np.degrees(np.arctan2(R[2, 1], R[2, 2]))
            yaw = np.degrees(np.arctan2(-R[2, 0], sy))
            roll = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
        else:  # Singular case
            pitch = np.degrees(np.arctan2(-R[1, 2], R[1, 1]))
            yaw = np.degrees(np.arctan2(-R[2, 0], sy))
            roll = 0
            
        return pitch, yaw, roll
        
    except Exception as e:
        print(f"Error converting rotation to euler angles: {e}")
        return 0, 0, 0
    
def smooth_head_pose(head_poses, new_pose):
    """Apply smoothing to head pose measurements to reduce jitter"""
    if not head_poses:
        return new_pose
    
    # Use a weighted average, giving more weight to newer measurements
    weights = [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]  # For last 10 frames
    if len(weights) > len(head_poses):
        weights = weights[-len(head_poses):]
        weights = [w/sum(weights) for w in weights]  # Normalize weights
    
    # Add new pose
    combined_poses = head_poses + [new_pose]
    if len(combined_poses) > len(weights):
        combined_poses = combined_poses[-len(weights):]
    
    # Calculate weighted average
    smoothed_pitch = sum(w * p[0] for w, p in zip(weights, combined_poses))
    smoothed_yaw = sum(w * p[1] for w, p in zip(weights, combined_poses))
    smoothed_roll = sum(w * p[2] for w, p in zip(weights, combined_poses))
    
    return (smoothed_pitch, smoothed_yaw, smoothed_roll)

def is_head_tilted(pitch, yaw, roll, baseline=(0, 0, 0)):
    """
    IMPROVED function to determine if head is tilted in a way that indicates drowsiness
    This updated version separates normal head tilt from drowsiness-indicating head movements
    Returns: (is_tilted, tilt_type, drowsiness_indicator)
    """
    # Adjust angles relative to baseline
    adj_pitch = pitch - baseline[0]
    adj_yaw = yaw - baseline[1]
    adj_roll = roll - baseline[2]
    
    # Initialize result variables
    is_tilted = False
    tilt_type = "Normal head position"
    drowsiness_indicator = False
    
    # IMPROVED LOGIC:
    # 1. First check for downward head nodding - the primary indicator of drowsiness
    if adj_pitch < DROWSY_PITCH_THRESHOLD:
        # Head is tilted significantly downward - this is the clearest sign of drowsiness
        is_tilted = True
        tilt_type = "Head nodding down (drowsiness)"
        drowsiness_indicator = True
    
    # 2. Check for extreme tilts in any direction that might be concerning
    elif abs(adj_pitch) > HEAD_PITCH_THRESHOLD * 1.3 or abs(adj_yaw) > HEAD_YAW_THRESHOLD * 1.3 or abs(adj_roll) > HEAD_ROLL_THRESHOLD * 1.3:
        is_tilted = True
        tilt_type = "Extreme head movement"
        # Only count as drowsiness if pitch is negative (nodding forward/down)
        drowsiness_indicator = (adj_pitch < 0)
        
    # 3. Normal tilts - not considered as drowsiness
    elif abs(adj_pitch) > HEAD_PITCH_THRESHOLD or abs(adj_yaw) > HEAD_YAW_THRESHOLD or abs(adj_roll) > HEAD_ROLL_THRESHOLD:
        is_tilted = True
        tilt_type = "Normal head movement"
        drowsiness_indicator = False
        
    return is_tilted, tilt_type, drowsiness_indicator

def visualize_head_pose(frame, rotation_vector, translation_vector, color=(255, 0, 0)):
    """Draw 3D axis to visualize head pose direction"""
    try:
        if rotation_vector is None or translation_vector is None:
            return frame
            
        axis_length = 50
        axis_points = np.array([
            [0, 0, 0],       # Origin
            [axis_length, 0, 0],  # X-axis
            [0, axis_length, 0],  # Y-axis
            [0, 0, axis_length]   # Z-axis
        ], dtype=np.float64)

        # Project 3D points to 2D image plane
        projected_points, _ = cv2.projectPoints(
            axis_points, rotation_vector, translation_vector,
            camera_matrix, dist_coeffs
        )
        
        # Draw axes
        origin = tuple(projected_points[0].ravel().astype(int))
        x_point = tuple(projected_points[1].ravel().astype(int))
        y_point = tuple(projected_points[2].ravel().astype(int))
        z_point = tuple(projected_points[3].ravel().astype(int))
        
        # Draw coordinate axes
        cv2.line(frame, origin, x_point, (0, 0, 255), 2)  # X-axis: Red
        cv2.line(frame, origin, y_point, (0, 255, 0), 2)  # Y-axis: Green
        cv2.line(frame, origin, z_point, (255, 0, 0), 2)  # Z-axis: Blue
        
        return frame
        
    except Exception as e:
        print(f"Error visualizing head pose: {e}")
        return frame

def play_alarm():
    """Function to play the alarm sound"""
    try:
        if SOUND_FILE:
            # Check if music is already playing
            if not pygame.mixer.music.get_busy():
                pygame.mixer.music.load(SOUND_FILE)
                pygame.mixer.music.play(-1)  # Play indefinitely
        else:
            # Use system beep as fallback
            print('\a')  # System beep
    except Exception as e:
        print(f"Error playing sound: {e}")
        # Try system beep as last resort
        print('\a')

def stop_alarm():
    """Function to stop the alarm sound"""
    try:
        pygame.mixer.music.stop()
    except Exception as e:
        print(f"Error stopping sound: {e}")

def calibrate_head_position(poses, num_frames=30):
    """Calculate the user's natural head position as baseline"""
    if len(poses) < num_frames:
        return None  # Not enough data to calibrate
        
    # Take the average of the poses as the baseline
    avg_pitch = sum(p[0] for p in poses) / len(poses)
    avg_yaw = sum(p[1] for p in poses) / len(poses)
    avg_roll = sum(p[2] for p in poses) / len(poses)
    
    return (avg_pitch, avg_yaw, avg_roll)

def check_arduino_status():
    """Function to periodically check Arduino connection status"""
    if arduino_connected and arduino_serial:
        try:
            # Only send if the serial buffer is empty
            if arduino_serial.out_waiting == 0:
                arduino_serial.write(b'STATUS\n')
                time.sleep(0.1)  # Give Arduino time to respond
                if arduino_serial.in_waiting > 0:
                    response = arduino_serial.readline().decode('utf-8', errors='ignore').strip()
                    if "STATUS:" in response:
                        return True
            return True  # Assume still connected if we just can't get a response now
        except Exception as e:
            print(f"Error checking Arduino status: {e}")
            return False
    return False

def send_warning():
    """Function to send warning command to Arduino"""
    if arduino_connected and arduino_serial:
        try:
            arduino_serial.write(b'WARNING\n')
            print("Warning sent to Arduino")
            
            # Wait for acknowledgment
            time.sleep(0.1)
            if arduino_serial.in_waiting > 0:
                response = arduino_serial.readline().decode('utf-8', errors='ignore').strip()
                if "WARNING_ACKNOWLEDGED" in response:
                    print("Warning acknowledged by Arduino")
        except Exception as e:
            print(f"Failed to send warning to Arduino: {e}")

def activate_brakes():
    """Function to send brake command to Arduino to stop the motor"""
    global braking_activated
    if braking_activated:
        return  # Already activated
    
    # Visual indication in console
    print("EMERGENCY: DROWSINESS DETECTED - STOPPING MOTOR")
    
    # Send command to Arduino
    if arduino_connected and arduino_serial:
        try:
            # Send command multiple times to ensure receipt
            for _ in range(3):
                arduino_serial.write(b'BRAKE\n')
                time.sleep(0.1)
            
            # Wait for acknowledgment
            response = arduino_serial.readline().decode('utf-8', errors='ignore').strip()
            if "BRAKE_ACKNOWLEDGED" in response:
                print("Stop motor command confirmed by Arduino")
            else:
                print(f"Unexpected response from Arduino: {response}")
        except Exception as e:
            print(f"Failed to send stop command to Arduino: {e}")
    
    braking_activated = True

def release_brakes():
    """Function to send brake release command to Arduino to resume motor"""
    global braking_activated
    if not braking_activated:
        return  # Already released
    
    # Visual indication in console
    print("ALERT CLEARED - RESUMING MOTOR")
    
    # Send command to Arduino
    if arduino_connected and arduino_serial:
        try:
            # Send command multiple times to ensure receipt
            for _ in range(3):
                arduino_serial.write(b'RELEASE\n')
                time.sleep(0.1)
            
            # Wait for acknowledgment
            response = arduino_serial.readline().decode('utf-8', errors='ignore').strip()
            if "RELEASE_ACKNOWLEDGED" in response:
                print("Motor resume command confirmed by Arduino")
            else:
                print(f"Unexpected response from Arduino: {response}")
        except Exception as e:
            print(f"Failed to send resume command to Arduino: {e}")
    
    braking_activated = False

def reset_alert_system():
    """Function to reset all alert timers and response flags"""
    global alert_start_time, driver_responded, braking_activated
    
    print("Alert system reset - driver response acknowledged")
    
    # Reset timers and flags
    alert_start_time = None
    driver_responded = True
    
    # Release brakes if they were activated
    if braking_activated:
        release_brakes()

# Define the indices for facial landmarks
RIGHT_EYE_POINTS = list(range(36, 42))  # 36-41 in zero-indexed
LEFT_EYE_POINTS = list(range(42, 48))   # 42-47 in zero-indexed
INNER_MOUTH_POINTS = list(range(60, 68)) # 60-67 in zero-indexed

# Main loop
frame_count = 0
calibration_poses = []

while True:
    try:
        # Calculate FPS
        current_time = time.time()
        fps = 1 / (current_time - last_frame_time)
        last_frame_time = current_time
        
        # Near the beginning of the main loop
        if frame_count % 100 == 0 and arduino_connected:  # Check every 100 frames
            if not check_arduino_status():
                print("Arduino connection lost - attempting to reconnect...")
                ARDUINO_PORT, arduino_serial, arduino_connected = connect_to_arduino()

        # Read frame with timeout handling
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame - trying to reinitialize camera")
            cap.release()
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("Could not reinitialize camera. Exiting.")
                break
            continue

        frame_count += 1
        if frame_count % 30 == 0:  # Log every 30 frames
            print(f"Processing frame {frame_count}, FPS: {fps:.2f}")

        # Convert frame to grayscale for processing
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect faces using dlib
        faces = detector(gray)
        
        # Flag to track if we found drowsiness in this frame
        drowsiness_detected = False
        drowsiness_reason = ""
        
        # If no faces detected, reset all timers
        if len(faces) == 0:
            eye_close_start_time = None
            yawn_start_time = None
            head_tilt_start_time = None
            if beep_playing:
                stop_alarm()
                beep_playing = False
        
        # Handle calibration mode display
        if head_tilt_baseline is None and calibration_frames < 60:
            cv2.putText(frame, "CALIBRATING - Please look straight at camera", 
                      (frame_width//2-200, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(frame, f"Progress: {calibration_frames}/60", 
                      (frame_width//2-100, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        for face in faces:
            # Predict facial landmarks
            landmarks = predictor(gray, face)
            
            # Convert landmarks to numpy array of coordinates
            landmark_points = []
            for i in range(68):  # 68 landmarks
                x = landmarks.part(i).x
                y = landmarks.part(i).y
                landmark_points.append((x, y))
            
            # Calculate center of face for head position tracking
            face_center_x = (face.left() + face.right()) // 2
            face_center_y = (face.top() + face.bottom()) // 2
            
            # Calculate EAR and MAR
            left_ear = calculate_ear(LEFT_EYE_POINTS, landmark_points)
            right_ear = calculate_ear(RIGHT_EYE_POINTS, landmark_points)
            ear = (left_ear + right_ear) / 2.0
            mar = calculate_mar(INNER_MOUTH_POINTS, landmark_points)
            
            # Estimate head pose
            pose_success, (pitch, yaw, roll), rotation_vector, translation_vector = detect_head_pose(landmarks, frame)
            
            # If in calibration mode, collect head pose data
            if head_tilt_baseline is None and pose_success:
                calibration_frames += 1
                
                # Store the pose for calibration
                if calibration_frames >= 15:  # Skip first few frames
                    calibration_poses.append((pitch, yaw, roll))
                
                # After collecting enough data, calculate baseline
                if calibration_frames >= 60:
                    head_tilt_baseline = calibrate_head_position(calibration_poses)
                    print(f"Calibration complete. Baseline: Pitch={head_tilt_baseline[0]:.2f}, Yaw={head_tilt_baseline[1]:.2f}, Roll={head_tilt_baseline[2]:.2f}")
            
            # Check if head is tilted (which could indicate drowsiness)
            baseline = head_tilt_baseline if head_tilt_baseline is not None else (0, 0, 0)
            head_tilted, tilt_message, drowsiness_tilt = is_head_tilted(pitch, yaw, roll, baseline) if pose_success else (False, "No pose data", False)
            
            # Draw visualization of head pose if detection was successful
            if pose_success:
                frame = visualize_head_pose(frame, rotation_vector, translation_vector)
                
                # Store head pose data for tracking
                head_poses.append((pitch, yaw, roll))
                if len(head_poses) > 10:  # Keep only recent positions
                    head_poses.pop(0)
                    
                # Draw head pose angles
                cv2.putText(frame, f"Pitch: {pitch:.1f}", (10, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Yaw: {yaw:.1f}", (10, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Roll: {roll:.1f}", (10, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Only show tilt as red if it indicates drowsiness
                tilt_color = (0, 0, 255) if drowsiness_tilt else (0, 255, 0)
                cv2.putText(frame, tilt_message, (10, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.7, tilt_color, 2)
            
            # Skip drowsiness detection during calibration
            if head_tilt_baseline is None:
                continue
            
            # Draw facial landmarks
            for i, (x, y) in enumerate(landmark_points):
                cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)
                
            # Draw eye and mouth landmarks with different colors
            for i in RIGHT_EYE_POINTS + LEFT_EYE_POINTS:
                x, y = landmark_points[i]
                cv2.circle(frame, (x, y), 2, (0, 0, 255), -1)
                
            for i in INNER_MOUTH_POINTS:
                x, y = landmark_points[i]
                cv2.circle(frame, (x, y), 2, (255, 0, 0), -1)
            
            # Draw bounding box around the face
            x1 = face.left()
            y1 = face.top()
            x2 = face.right()
            y2 = face.bottom()
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Display EAR and MAR values
            cv2.putText(frame, f"EAR: {ear:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                        (0, 0, 255) if ear < EAR_THRESHOLD else (0, 255, 0), 2)
            cv2.putText(frame, f"MAR: {mar:.2f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                        (0, 0, 255) if mar > MAR_THRESHOLD else (0, 255, 0), 2)
            
            # IMPROVED: More informative display for drowsiness indicators
            head_tilt_status = "DOWN (Drowsy)" if drowsiness_tilt else "Normal"
            cv2.putText(frame, f"Head Position: {head_tilt_status}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                        (0, 0, 255) if drowsiness_tilt else (0, 255, 0), 2)
            
            # ===================== IMPROVED Drowsiness Detection Logic =====================
            
            # 1. Eye Closure Detection
            eyes_closed = ear < EAR_THRESHOLD
            if eyes_closed:
                if eye_close_start_time is None:
                    eye_close_start_time = time.time()
                elif time.time() - eye_close_start_time > TIME_THRESHOLD:
                    drowsiness_detected = True
                    drowsiness_reason = "EYE CLOSURE"
            else:
                eye_close_start_time = None
            
            # 2. Yawning Detection
            yawning = mar > MAR_THRESHOLD
            if yawning:
                if yawn_start_time is None:
                    yawn_start_time = time.time()
                elif time.time() - yawn_start_time > TIME_THRESHOLD:
                    drowsiness_detected = True
                    drowsiness_reason = "YAWNING"
            else:
                yawn_start_time = None
            
            # 3. IMPROVED Head Tilt Detection Logic
            # Only track downward head motion (pitch < threshold) as true drowsiness indicator
            if pose_success and drowsiness_tilt:
                if head_tilt_start_time is None:
                    head_tilt_start_time = time.time()
                # Use a longer threshold for head tilt drowsiness detection to reduce false positives
                elif time.time() - head_tilt_start_time > DROWSY_HEAD_DURATION:
                    drowsiness_detected = True
                    drowsiness_reason = "HEAD NODDING DOWN"
            else:
                head_tilt_start_time = None
            
            # 4. Combined Detection (multiple indicators)
            # Only consider combinations that include "real" drowsiness indicators
            if (eyes_closed and yawning) or (eyes_closed and drowsiness_tilt) or (yawning and drowsiness_tilt):
                # If multiple indicators occur together, detect drowsiness faster
                drowsiness_detected = True
                drowsiness_reason = "MULTIPLE INDICATORS"

            # In your AUTO-BRAKING SYSTEM LOGIC section
            if drowsiness_detected:
                # If this is a new alert, start the timer
                if alert_start_time is None:
                    alert_start_time = time.time()
                    driver_responded = False
                    print(f"Drowsiness alert started: {drowsiness_reason}")
        
                    # Send warning to Arduino before full braking
                    if arduino_connected and arduino_serial:
                        send_warning()
    
                # Check if driver has not responded for the timeout period
                if not driver_responded and (time.time() - alert_start_time > ALERT_TIMEOUT) and not braking_activated:
                    # Activate emergency braking system
                    activate_brakes()
            
            # Display detection status on frame
            # if drowsiness_detected:
            #     cv2.putText(frame, f"DROWSINESS DETECTED: {
            #         # Display detection status on frame
            if drowsiness_detected:
                cv2.putText(frame, f"DROWSINESS DETECTED: {drowsiness_reason}", (10, 90), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                # Play alert sound
                if not beep_playing:
                    play_alarm()
                    beep_playing = True
                
                # Show auto-brake warning if close to timeout
                if alert_start_time is not None and not driver_responded:
                    elapsed_time = time.time() - alert_start_time
                    remaining_time = max(0, ALERT_TIMEOUT - elapsed_time)
                    
                    # Display countdown to auto-braking
                    cv2.putText(frame, f"AUTO-BRAKE in: {remaining_time:.1f}s", 
                              (frame_width//2-150, frame_height-50), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
                    
                    # Make warning more prominent as timeout approaches
                    if remaining_time < 2.0:
                        # Add flashing red box
                        alpha = 0.3  # Transparency
                        overlay = frame.copy()
                        cv2.rectangle(overlay, (0, 0), (frame_width, frame_height), (0, 0, 255), -1)
                        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
                        
                        # Add MORE PROMINENT warning text
                        cv2.putText(frame, "WAKE UP! AUTO-BRAKING IMMINENT!", 
                                  (frame_width//2-250, frame_height//2), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
            else:
                # Stop alert if no drowsiness detected
                if beep_playing:
                    stop_alarm()
                    beep_playing = False

        # Display auto-braking status if active
        if braking_activated:
            # Draw red border around frame
            cv2.rectangle(frame, (0, 0), (frame_width, frame_height), (0, 0, 255), 20)
            # Display emergency braking text
            cv2.putText(frame, "EMERGENCY BRAKING ACTIVATED", 
                      (frame_width//2-250, frame_height//2), 
                      cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            cv2.putText(frame, "Press 'r' to reset system", 
                      (frame_width//2-150, frame_height//2+40), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # Display instructions
        cv2.putText(frame, "Press 'r' to respond to alert", (10, frame_height-70), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, "Press 'q' to quit", (10, frame_height-40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Display frame
        cv2.imshow("Drowsiness Detection with Auto-Braking", frame)
        
        # Key handling
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            # Driver responded to alert - reset alert system
            if alert_start_time is not None or braking_activated:
                reset_alert_system()
                if braking_activated:
                    release_brakes()
                    braking_activated = False
                print("Driver manually responded to alert")
                
    except Exception as e:
        print(f"Error in main loop: {e}")
        # Add a small delay to prevent CPU overload in case of errors
        time.sleep(0.1)

# Cleanup
# Cleanup
print("Shutting down system...")
try:
    cap.release()
    cv2.destroyAllWindows()
    stop_alarm()
    
    # Release brakes if they were activated
    if braking_activated:
        release_brakes()
    
    # Close Arduino connection if it was opened
    if arduino_connected and arduino_serial:
        # Make sure to send a final release command
        arduino_serial.write(b'RELEASE\n')
        time.sleep(0.5)  # Give Arduino time to process
        arduino_serial.close()
        print("Arduino connection closed")
        
except Exception as e:
    print(f"Error during cleanup: {e}")

print("System shutdown complete")