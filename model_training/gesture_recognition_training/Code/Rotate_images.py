import cv2
import os

def flip_images():
    gest_folder = "gestures"

    for g_id in os.listdir(gest_folder):

        folder_path = os.path.join(gest_folder, g_id)

        image_files = [
            f for f in os.listdir(folder_path)
            if f.endswith(".jpg")
        ]

        total_images = len(image_files)

        print(f"Found {total_images} images in gesture {g_id}")

        for i in range(total_images):

            path = os.path.join(folder_path, f"{i+1}.jpg")

            if not os.path.exists(path):
                continue

            img = cv2.imread(path, 0)

            if img is None:
                print(f"Could not read: {path}")
                continue

            flipped = cv2.flip(img, 1)

            new_path = os.path.join(
                folder_path,
                f"{i+1+total_images}.jpg"
            )

            cv2.imwrite(new_path, flipped)

            print(f"Saved flipped image: {new_path}")

    print("Done flipping images.")


flip_images()
