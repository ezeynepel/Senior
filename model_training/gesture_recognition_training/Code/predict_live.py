import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import cv2
import numpy as np
import pickle
import requests
import time
from datetime import datetime, timezone
from collections import deque, Counter
from keras.models import load_model

BASE_PATH = r"C:\Users\Taha\Desktop\Sign-Language-Interpreter-using-Deep-Learning-master\Sign-Language-Interpreter-using-Deep-Learning-master"

image_x, image_y = 50, 50

ARIS_API = "http://127.0.0.1:8000/api/v1/commands"
CAMERA_UPLOAD_API = "http://127.0.0.1:8000/api/v1/camera/upload"

DEVICE_ID = "helmet_01"
SESSION_ID = "sess_helmet_01"

GESTURE_MAP = {
    1: "UC",
    2: "IKI",
    3: "DUR",
    4: "DUR",
    5: "DUR",
    6: "IYI_IS"
}

MIN_HAND_RATIO = 0.005
MAX_HAND_RATIO = 0.80
MIN_CONTOUR_AREA = 500
CONFIDENCE_THRESHOLD = 20

STABLE_FRAME_COUNT = 12
MIN_STABLE_COUNT = 8

SEND_COOLDOWN_SECONDS = 2
last_send_time = 0


def send_frame_to_backend(frame):
    success, jpeg = cv2.imencode(".jpg", frame)

    if not success:
        return

    try:
        requests.post(
            CAMERA_UPLOAD_API,
            data=jpeg.tobytes(),
            headers={"Content-Type": "application/octet-stream"},
            timeout=0.1
        )
    except:
        pass


def send_to_aris(command, confidence=0.95):
    payload = {
        "device_id": DEVICE_ID,
        "session_id": SESSION_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command_type": command.upper().replace(" ", "_"),
        "source": "gesture",
        "confidence_score": round(float(confidence) / 100, 2),
        "priority": "medium",
        "status": "validated"
    }

    try:
        response = requests.post(ARIS_API, json=payload, timeout=1)
        print("ARIS gönderildi:", payload["command_type"], response.status_code)
    except Exception as e:
        print("ARIS backend gönderilemedi:", e)


def get_hand_hist():
    with open(os.path.join(BASE_PATH, "Code", "hist"), "rb") as f:
        return pickle.load(f)


def open_camera():
    cam_index = 1

    cam = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    ret, frame = cam.read()

    if ret and frame is not None:
        print(f"Logitech camera opened. Index: {cam_index}")
        return cam

    cam.release()
    print("Logitech kamera index 1 ile açılamadı.")

    cam_index = 0
    cam = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    ret, frame = cam.read()

    if ret and frame is not None:
        print(f"Default camera opened. Index: {cam_index}")
        return cam

    cam.release()
    return None


def preprocess_hand(thresh_roi):
    hand_mask = 255 - thresh_roi
    hand_ratio = cv2.countNonZero(hand_mask) / hand_mask.size

    if hand_ratio < MIN_HAND_RATIO or hand_ratio > MAX_HAND_RATIO:
        return None

    contours_result = cv2.findContours(
        hand_mask.copy(),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    contours = contours_result[1] if len(contours_result) == 3 else contours_result[0]

    if len(contours) == 0:
        return None

    contour = max(contours, key=cv2.contourArea)

    if cv2.contourArea(contour) < MIN_CONTOUR_AREA:
        return None

    x1, y1, w1, h1 = cv2.boundingRect(contour)
    save_img = hand_mask[y1:y1+h1, x1:x1+w1]

    if save_img.size == 0:
        return None

    if w1 > h1:
        diff = int((w1 - h1) / 2)
        save_img = cv2.copyMakeBorder(
            save_img, diff, diff, 0, 0,
            cv2.BORDER_CONSTANT,
            value=0
        )
    elif h1 > w1:
        diff = int((h1 - w1) / 2)
        save_img = cv2.copyMakeBorder(
            save_img, 0, 0, diff, diff,
            cv2.BORDER_CONSTANT,
            value=0
        )

    save_img = cv2.resize(save_img, (image_x, image_y))
    save_img = 255 - save_img

    debug_img = save_img.copy()

    model_img = save_img.astype("float32") / 255.0
    model_img = np.reshape(model_img, (1, image_x, image_y, 1))

    return model_img, debug_img


hist = get_hand_hist()
model = load_model(os.path.join(BASE_PATH, "cnn_model_keras2.h5"))

with open(os.path.join(BASE_PATH, "label_mapping.pkl"), "rb") as f:
    INDEX_TO_LABEL = pickle.load(f)

print("Loaded label mapping:", INDEX_TO_LABEL)

cam = open_camera()

if cam is None:
    print("Kamera açılamadı.")
    exit()

x, y, w, h = 300, 100, 300, 300

prediction_buffer = deque(maxlen=STABLE_FRAME_COUNT)
last_confirmed_text = ""
display_text = "WAITING..."

while True:
    ret, img = cam.read()

    if not ret or img is None:
        print("Kameradan görüntü alınamadı.")
        break

    img = cv2.flip(img, 1)

    img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    dst = cv2.calcBackProject(
        [img_hsv],
        [0, 1],
        hist,
        [0, 180, 0, 256],
        1
    )

    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (10, 10))
    cv2.filter2D(dst, -1, disc, dst)

    blur = cv2.GaussianBlur(dst, (5, 5), 0)
    blur = cv2.medianBlur(blur, 5)

    thresh = cv2.threshold(
        blur,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )[1]

    thresh_roi = thresh[y:y+h, x:x+w]

    result = preprocess_hand(thresh_roi)

    instant_text = "NO_HAND"
    instant_prediction_text = "No hand detected"
    current_confidence = 0.0

    if result is not None:
        processed_img, debug_img = result

        pred = model.predict(processed_img, verbose=0)[0]

        pred_class = int(np.argmax(pred))
        confidence = float(np.max(pred)) * 100
        current_confidence = confidence

        gesture_id = int(INDEX_TO_LABEL[pred_class])

        if gesture_id in GESTURE_MAP:
            if confidence >= CONFIDENCE_THRESHOLD:
                instant_text = GESTURE_MAP[gesture_id]
                instant_prediction_text = f"Prediction: {instant_text} ({confidence:.2f}%)"
            else:
                instant_text = "LOW_CONF"
                instant_prediction_text = f"Low confidence: {GESTURE_MAP[gesture_id]} ({confidence:.2f}%)"
        else:
            instant_text = "IGNORED"
            instant_prediction_text = f"Ignored gesture: {gesture_id} ({confidence:.2f}%)"

    prediction_buffer.append(instant_text)

    if len(prediction_buffer) == STABLE_FRAME_COUNT:
        most_common_text, stable_count = Counter(prediction_buffer).most_common(1)[0]

        invalid_outputs = ["LOW_CONF", "NO_HAND", "IGNORED"]

        if stable_count >= MIN_STABLE_COUNT:
            display_text = most_common_text

            if most_common_text in invalid_outputs:
                last_confirmed_text = ""
            else:
                if display_text != last_confirmed_text:
                    print(f"Predicted text = {display_text}")

                    now = time.time()
                    if now - last_send_time >= SEND_COOLDOWN_SECONDS:
                        send_to_aris(display_text, current_confidence)
                        last_send_time = now

                    last_confirmed_text = display_text

    cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)

    cv2.putText(
        img,
        instant_prediction_text,
        (30, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 255),
        2
    )

    cv2.putText(
        img,
        "Confirmed text = " + display_text,
        (30, 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2
    )

    send_frame_to_backend(img)

    cv2.imshow("Live Prediction", img)
    cv2.imshow("Threshold", 255-thresh_roi)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q") or key == 27:
        break

cam.release()
cv2.destroyAllWindows()