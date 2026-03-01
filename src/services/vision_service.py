import cv2
import mediapipe as mp
import numpy as np
from scipy.spatial import distance as dist
from src import config

class VisionService:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=config.MP_MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.MP_MIN_TRACKING_CONFIDENCE
        )
        self.camera_matrix = None
        self.dist_coeffs = np.zeros((4, 1))
        
        # MediaPipe Landmark Indices
        # Left Eye (Upper, Lower, Left, Right)
        self.LEFT_EYE = [160, 144, 158, 153, 33, 133] 
        # Right Eye
        self.RIGHT_EYE = [385, 373, 387, 380, 362, 263]
        # Mouth (Inner lips for MAR)
        self.MOUTH = [13, 14, 78, 308] # Upper, Lower, Left, Right

    def init_camera(self, width, height):
        focal_length = width
        center = (width / 2, height / 2)
        self.camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float64)

    def process_frame(self, frame):
        """Returns the mesh results"""
        # MediaPipe needs RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False
        results = self.face_mesh.process(rgb_frame)
        rgb_frame.flags.writeable = True
        return results

    def get_landmarks_array(self, frame, results):
        """Converts normalized landmarks to pixel coordinates (x, y)"""
        if not results.multi_face_landmarks:
            return None
        
        # We only take the first face
        face_landmarks = results.multi_face_landmarks[0]
        h, w, _ = frame.shape
        points = []
        for lm in face_landmarks.landmark:
            points.append((int(lm.x * w), int(lm.y * h)))
        return np.array(points)

    def calculate_ear(self, eye_indices, landmarks):
        # Vertical lines
        A = dist.euclidean(landmarks[eye_indices[0]], landmarks[eye_indices[1]])
        B = dist.euclidean(landmarks[eye_indices[2]], landmarks[eye_indices[3]])
        # Horizontal line
        C = dist.euclidean(landmarks[eye_indices[4]], landmarks[eye_indices[5]])
        return (A + B) / (2.0 * C) if C != 0 else 0.0

    def calculate_mar(self, mouth_indices, landmarks):
        # Vertical (Upper to Lower)
        A = dist.euclidean(landmarks[mouth_indices[0]], landmarks[mouth_indices[1]])
        # Horizontal (Left to Right)
        C = dist.euclidean(landmarks[mouth_indices[2]], landmarks[mouth_indices[3]])
        return A / C if C != 0 else 0.0

    def get_head_pose(self, landmarks):
        # 3D Model Points (Generic Face)
        model_points = np.array([
            (0.0, 0.0, 0.0),             # Nose tip
            (0.0, -330.0, -65.0),        # Chin
            (-225.0, 170.0, -135.0),     # Left eye left corner
            (225.0, 170.0, -135.0),      # Right eye right corner
            (-150.0, -150.0, -125.0),    # Left mouth corner
            (150.0, -150.0, -125.0)      # Right mouth corner
        ])

        # Image Points from Landmarks (Indices must match model points)
        # Nose(1), Chin(152), LeftEye(33), RightEye(263), LeftMouth(61), RightMouth(291)
        image_points = np.array([
            landmarks[1],
            landmarks[152],
            landmarks[33],
            landmarks[263],
            landmarks[61],
            landmarks[291]
        ], dtype="double")

        success, rvec, tvec = cv2.solvePnP(
            model_points, image_points, self.camera_matrix, self.dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if not success:
            return False, (0,0,0), None, None

        rmat, _ = cv2.Rodrigues(rvec)
        pitch, yaw, roll = self._rmat_to_euler(rmat)
        return True, (pitch, yaw, roll), rvec, tvec
def _rmat_to_euler(self, R):
    sy = np.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
    if sy > 1e-6:
        pitch = np.degrees(np.arctan2(R[2, 1], R[2, 2]))
        yaw = np.degrees(np.arctan2(-R[2, 0], sy))
        roll = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
    else:
        pitch = np.degrees(np.arctan2(-R[1, 2], R[1, 1]))
        yaw = np.degrees(np.arctan2(-R[2, 0], sy))
        roll = 0
    return pitch, yaw, roll

def draw_landmarks(self, frame, landmarks):
    for pt in landmarks:
        cv2.circle(frame, tuple(pt), 1, (0, 255, 0), -1)

    # Highlight eyes
    for idx in self.LEFT_EYE + self.RIGHT_EYE:
        cv2.circle(frame, tuple(landmarks[idx]), 2, (0, 0, 255), -1)

def draw_pose_axis(self, frame, rvec, tvec):
    axis_length = 50
    axis_points = np.array([[0,0,0], [axis_length,0,0], [0,axis_length,0], [0,0,axis_length]], dtype=np.float64)
    proj_pts, _ = cv2.projectPoints(axis_points, rvec, tvec, self.camera_matrix, self.dist_coeffs)
    origin = tuple(proj_pts[0].ravel().astype(int))
    cv2.line(frame, origin, tuple(proj_pts[1].ravel().astype(int)), (0,0,255), 2)
    cv2.line(frame, origin, tuple(proj_pts[2].ravel().astype(int)), (0,255,0), 2)
    cv2.line(frame, origin, tuple(proj_pts[3].ravel().astype(int)), (255,0,0), 2)
    return frame

            roll = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
        else:
            pitch = np.degrees(np.arctan2(-R[1, 2], R[1, 1]))
            yaw = np.degrees(np.arctan2(-R[2, 0], sy))
            roll = 0
        return pitch, yaw, roll

    def draw_pose_axis(self, frame, rvec, tvec):
        axis_length = 50
        axis_points = np.array([[0,0,0], [axis_length,0,0], [0,axis_length,0], [0,0,axis_length]], dtype=np.float64)
        proj_pts, _ = cv2.projectPoints(axis_points, rvec, tvec, self.camera_matrix, self.dist_coeffs)
        origin = tuple(proj_pts[0].ravel().astype(int))
        cv2.line(frame, origin, tuple(proj_pts[1].ravel().astype(int)), (0,0,255), 2)
        cv2.line(frame, origin, tuple(proj_pts[2].ravel().astype(int)), (0,255,0), 2)
        cv2.line(frame, origin, tuple(proj_pts[3].ravel().astype(int)), (255,0,0), 2)
        return frame
