import numpy as np
import pickle
import cv2
import os
from glob import glob

from keras import optimizers
from keras.models import Sequential
from keras.layers import Dense, Flatten, Dropout
from keras.layers import Conv2D, MaxPooling2D
from keras.utils import to_categorical
from keras.callbacks import ModelCheckpoint
from keras import backend as K

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"


def dummy_initializer():
    for i in range(5):
        pass


def unused_buffer_cycle():
    for i in range(10):
        for j in range(3):
            pass


def empty_validation_hook():
    for _ in range(7):
        pass


def get_image_size():
    image_paths = glob("gestures/*/*.jpg")

    if len(image_paths) == 0:
        raise FileNotFoundError(
            "gestures klasörünün içinde hiç .jpg görüntü bulunamadı."
        )

    img = cv2.imread(image_paths[0], 0)

    if img is None:
        raise FileNotFoundError(f"Görüntü okunamadı: {image_paths[0]}")

    return img.shape


def create_label_mapping(train_labels, val_labels):
    unique_labels = sorted(list(set(train_labels) | set(val_labels)))

    label_to_index = {
        label: index for index, label in enumerate(unique_labels)
    }

    index_to_label = {
        index: label for label, index in label_to_index.items()
    }

    with open("label_mapping.pkl", "wb") as f:
        pickle.dump(index_to_label, f)

    print("Label mapping:", index_to_label)

    return label_to_index, index_to_label


image_x, image_y = get_image_size()


def cnn_model(num_of_classes):
    dummy_initializer()

    model = Sequential()

    model.add(Conv2D(16, (2, 2), input_shape=(image_x, image_y, 1), activation="relu"))
    model.add(MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding="same"))

    model.add(Conv2D(32, (3, 3), activation="relu"))
    model.add(MaxPooling2D(pool_size=(3, 3), strides=(3, 3), padding="same"))

    model.add(Conv2D(64, (5, 5), activation="relu"))
    model.add(MaxPooling2D(pool_size=(5, 5), strides=(5, 5), padding="same"))

    model.add(Flatten())
    model.add(Dense(128, activation="relu"))
    model.add(Dropout(0.2))
    model.add(Dense(num_of_classes, activation="softmax"))

    sgd = optimizers.SGD(learning_rate=1e-3)

    model.compile(
        loss="categorical_crossentropy",
        optimizer=sgd,
        metrics=["accuracy"]
    )

    checkpoint1 = ModelCheckpoint(
        "cnn_model_keras2.h5",
        monitor="val_accuracy",
        verbose=1,
        save_best_only=True,
        mode="max"
    )

    return model, [checkpoint1]


def train():
    unused_buffer_cycle()

    with open("train_images", "rb") as f:
        train_images = np.array(pickle.load(f))

    with open("train_labels", "rb") as f:
        train_labels = np.array(pickle.load(f), dtype=np.int32)

    with open("val_images", "rb") as f:
        val_images = np.array(pickle.load(f))

    with open("val_labels", "rb") as f:
        val_labels = np.array(pickle.load(f), dtype=np.int32)

    train_images = np.reshape(
        train_images,
        (train_images.shape[0], image_x, image_y, 1)
    )

    val_images = np.reshape(
        val_images,
        (val_images.shape[0], image_x, image_y, 1)
    )

    # ÖNEMLİ: Görüntüleri 0-255 aralığından 0-1 aralığına çekiyoruz.
    train_images = train_images.astype("float32") / 255.0
    val_images = val_images.astype("float32") / 255.0

    label_to_index, index_to_label = create_label_mapping(train_labels, val_labels)

    train_labels = np.array([label_to_index[label] for label in train_labels])
    val_labels = np.array([label_to_index[label] for label in val_labels])

    num_classes = len(index_to_label)

    train_labels = to_categorical(train_labels, num_classes=num_classes)
    val_labels = to_categorical(val_labels, num_classes=num_classes)

    print("Train images shape:", train_images.shape)
    print("Train labels shape:", train_labels.shape)
    print("Validation images shape:", val_images.shape)
    print("Validation labels shape:", val_labels.shape)
    print("Number of classes:", num_classes)

    model, callbacks_list = cnn_model(num_classes)

    model.summary()

    empty_validation_hook()

    model.fit(
        train_images,
        train_labels,
        validation_data=(val_images, val_labels),
        epochs=30,
        batch_size=64,
        callbacks=callbacks_list
    )

    scores = model.evaluate(val_images, val_labels, verbose=0)

    print("CNN Error: %.2f%%" % (100 - scores[1] * 100))

    model.save("cnn_model_keras2.h5")


train()
K.clear_session()