import cv2
import numpy as np
import pickle
import os
import sqlite3
import random

image_x, image_y = 50, 50


def get_hand_hist():
    with open("hist", "rb") as f:
        hist = pickle.load(f)
    return hist


def init_create_folder_database():
    if not os.path.exists("gestures"):
        os.mkdir("gestures")

    if not os.path.exists("gesture_db.db"):
        conn = sqlite3.connect("gesture_db.db")
        create_table_cmd = """
        CREATE TABLE gesture (
            g_id INTEGER NOT NULL PRIMARY KEY UNIQUE,
            g_name TEXT NOT NULL
        )
        """
        conn.execute(create_table_cmd)
        conn.commit()
        conn.close()


def create_folder(folder_name):
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)


def store_in_db(g_id, g_name):
    conn = sqlite3.connect("gesture_db.db")

    try:
        conn.execute(
            "INSERT INTO gesture (g_id, g_name) VALUES (?, ?)",
            (g_id, g_name)
        )
    except sqlite3.IntegrityError:
        choice = input("g_id already exists. Want to change the record? (y/n): ")
        if choice.lower() == "y":
            conn.execute(
                "UPDATE gesture SET g_name = ? WHERE g_id = ?",
                (g_name, g_id)
            )
        else:
            print("Doing nothing...")
            conn.close()
            return

    conn.commit()
    conn.close()


def open_camera():
    for cam_index in [0, 1, 2, 3]:
        cam = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        ret, frame = cam.read()

        if ret and frame is not None:
            print(f"Camera opened successfully. Camera index: {cam_index}")
            return cam

        cam.release()

    print("No camera found.")
    return None


def get_contours(thresh):
    contours_result = cv2.findContours(
        thresh.copy(),
        cv2.RETR_TREE,
        cv2.CHAIN_APPROX_NONE
    )

    if len(contours_result) == 3:
        contours = contours_result[1]
    else:
        contours = contours_result[0]

    return contours


def store_images(g_id):
    total_pics = 1200
    hist = get_hand_hist()

    cam = open_camera()
    if cam is None:
        return

    x, y, w, h = 300, 100, 300, 300

    create_folder("gestures/" + str(g_id))

    pic_no = 0
    flag_start_capturing = False
    frames = 0

    while True:
        ret, img = cam.read()

        if not ret or img is None:
            print("Camera frame could not be read.")
            break

        img = cv2.flip(img, 1)

        imgHSV = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        dst = cv2.calcBackProject(
            [imgHSV],
            [0, 1],
            hist,
            [0, 180, 0, 256],
            1
        )

        disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (10, 10))
        cv2.filter2D(dst, -1, disc, dst)

        blur = cv2.GaussianBlur(dst, (11, 11), 0)
        blur = cv2.medianBlur(blur, 15)

        thresh = cv2.threshold(
            blur,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]

        thresh = cv2.merge((thresh, thresh, thresh))
        thresh = cv2.cvtColor(thresh, cv2.COLOR_BGR2GRAY)

        thresh_roi = thresh[y:y + h, x:x + w]

        contours = get_contours(thresh_roi)

        if len(contours) > 0:
            contour = max(contours, key=cv2.contourArea)

            if cv2.contourArea(contour) > 10000 and frames > 50:
                x1, y1, w1, h1 = cv2.boundingRect(contour)

                save_img = thresh_roi[y1:y1 + h1, x1:x1 + w1]

                if save_img.size != 0:
                    pic_no += 1

                    if w1 > h1:
                        diff = int((w1 - h1) / 2)
                        save_img = cv2.copyMakeBorder(
                            save_img,
                            diff,
                            diff,
                            0,
                            0,
                            cv2.BORDER_CONSTANT,
                            value=(0, 0, 0)
                        )
                    elif h1 > w1:
                        diff = int((h1 - w1) / 2)
                        save_img = cv2.copyMakeBorder(
                            save_img,
                            0,
                            0,
                            diff,
                            diff,
                            cv2.BORDER_CONSTANT,
                            value=(0, 0, 0)
                        )

                    save_img = cv2.resize(save_img, (image_x, image_y))

                    rand = random.randint(0, 10)
                    if rand % 2 == 0:
                        save_img = cv2.flip(save_img, 1)

                    cv2.imwrite(
                        "gestures/" + str(g_id) + "/" + str(pic_no) + ".jpg",
                        save_img
                    )

                    cv2.putText(
                        img,
                        "Capturing...",
                        (30, 60),
                        cv2.FONT_HERSHEY_TRIPLEX,
                        2,
                        (127, 255, 255),
                        2
                    )
        else:
            cv2.putText(
                img,
                "No hand detected",
                (30, 60),
                cv2.FONT_HERSHEY_TRIPLEX,
                1,
                (0, 0, 255),
                2
            )

        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

        cv2.putText(
            img,
            "Images: " + str(pic_no),
            (30, 400),
            cv2.FONT_HERSHEY_TRIPLEX,
            1.5,
            (127, 127, 255),
            2
        )

        if not flag_start_capturing:
            cv2.putText(
                img,
                "Press C to start capturing",
                (30, 450),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2
            )
        else:
            cv2.putText(
                img,
                "Press C to pause, Q to quit",
                (30, 450),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2
            )

        cv2.imshow("Capturing gesture", img)
        cv2.imshow("thresh", thresh_roi)

        keypress = cv2.waitKey(1) & 0xFF

        if keypress == ord("c"):
            flag_start_capturing = not flag_start_capturing
            if not flag_start_capturing:
                frames = 0

        if keypress == ord("q") or keypress == 27:
            break

        if flag_start_capturing:
            frames += 1

        if pic_no >= total_pics:
            break

    cam.release()
    cv2.destroyAllWindows()


init_create_folder_database()

g_id = input("Enter gesture no.: ")
g_name = input("Enter gesture name/text: ")

store_in_db(g_id, g_name)
store_images(g_id)