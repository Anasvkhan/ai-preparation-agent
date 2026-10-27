"""Face matching service for the Smart Attendance System."""
import numpy as np

SIMILARITY_THRESHOLD = 0.75
MIN_FRAMES_FOR_PRESENT = 3


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def match_face(embedding, enrolled):
    """Return the student id with the highest similarity above the threshold, else None."""
    best_id, best_score = None, SIMILARITY_THRESHOLD
    for student_id, template in enrolled.items():
        score = cosine_similarity(embedding, template)
        if score > best_score:
            best_id, best_score = student_id, score
    return best_id


def update_attendance(counts, student_id):
    """Count recognised frames; a student is present after MIN_FRAMES_FOR_PRESENT frames."""
    counts[student_id] = counts.get(student_id, 0) + 1
    return counts[student_id] >= MIN_FRAMES_FOR_PRESENT
