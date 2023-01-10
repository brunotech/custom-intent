import json
import os
import pickle
import random
from collections import OrderedDict
from pathlib import Path
from time import perf_counter

import keras
import numpy as np
import tensorflow as tf

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import nltk
from nltk.stem import WordNetLemmatizer

from keras_preprocessing.image import img_to_array
from tensorflow.python.keras.models import Sequential
from tensorflow.python.keras.layers import Dense, Dropout, MaxPooling2D, Flatten, \
    Conv2D, GlobalAveragePooling2D, Activation
from tensorflow.python.keras import layers
from tensorflow.python.keras.optimizer_v2.gradient_descent import SGD
from tensorflow.python.keras.models import load_model
from tensorflow.python.keras.optimizer_v2.adam import Adam
from tensorflow.python.keras.optimizer_v2.adamax import Adamax
from tensorflow.python.keras.optimizer_v2.adagrad import Adagrad
from tensorflow.python.keras.metrics import Precision, Recall, BinaryAccuracy

from random import random

import wandb
from wandb.keras import WandbCallback
import matplotlib.pyplot as plt

import imghdr
import cv2.load_config_py2
import cv2
import csv

from threading import Thread

from functools import wraps

from numba import njit, jit
from collections import Counter

import Pfunctions

from Bcolor import bcolors


def timeit(func):
    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        start_time = perf_counter()
        result = func(*args, **kwargs)
        end_time = perf_counter()
        total_time = end_time - start_time
        # first item in the args, ie `args[0]` is `self`
        print(f'Function {func.__name__} Took {total_time:.4f} seconds')
        return result

    return timeit_wrapper


class VideoStream:

    def __init__(self, src=0):
        self.stream = cv2.VideoCapture(src)
        (self.grabbed, self.frame) = self.stream.read()
        self.stopped = False

    def start(self):
        Thread(target=self.update, args=()).start()
        return self

    def update(self):
        while True:
            if self.stopped:
                return
            (self.grabbed, self.frame) = self.stream.read()

    def read(self):
        # Return the latest frame
        return self.frame

    def stop(self):
        self.stopped = True


class BinaryImageClassificate:
    def __init__(self, data_folder="data", model_name="imageclassification_model", first_class="1", second_class="2"):
        self.optimizer = None
        self.acc = None
        self.re = None
        self.pre = None
        self.first_class = first_class
        self.second_class = second_class
        self.tensorboard_callback = None
        self.logdir = None
        self.model = None
        self.batch = None
        self.test = None
        self.val = None
        self.train = None
        self.test_size = None
        self.val_size = None
        self.train_size = None
        self.data_iterator = None
        self.hist = None
        self.data_folder = data_folder
        self.name = model_name
        self.data = None
        self.oom_avoider()

    def remove_dogy_images(self):
        data_dir = self.data_folder
        image_exts = ['jpeg', 'jpg', 'bmp', 'png']
        for image_class in os.listdir(data_dir):
            for image in os.listdir(os.path.join(data_dir, image_class)):
                image_path = os.path.join(data_dir, image_class, image)
                try:
                    img = cv2.imread(image_path)
                    tip = imghdr.what(image_path)
                    if tip not in image_exts:
                        print('Image not in ext list {}'.format(image_path))
                        os.remove(image_path)
                except Exception as e:
                    print('Issue with image {}'.format(image_path))
                    os.remove(image_path)

    def load_data(self):
        self.data = tf.keras.utils.image_dataset_from_directory(self.data_folder)
        self.data_iterator = self.data.as_numpy_iterator()
        self.batch = self.data_iterator.next()
        print(f"{bcolors.OKGREEN}loading data succsesfuly{bcolors.ENDC}")

    def scale_data(self, model_type="s1"):
        self.data = self.data.map(lambda x, y: (x / 255, y))
        print(f"{bcolors.OKGREEN}scaling data succsesfuly{bcolors.ENDC}")

    def augmanet_data(self, model_type="s1"):
        if "a" in model_type:
            data_augmentation = Sequential([
                tf.keras.layers.RandomFlip(mode="horizontal"),
                tf.keras.layers.RandomRotation((-0.3, 0.3)),
                tf.keras.layers.RandomZoom(height_factor=(-0.1, 0.1)),
                tf.keras.layers.RandomBrightness(factor=0.2)
            ])
            self.data = self.data.map(lambda x, y: (data_augmentation(x, training=True), y),
                                      num_parallel_calls=tf.data.AUTOTUNE)
            print(f"{bcolors.OKGREEN}augmenting data succsesfuly{bcolors.ENDC}")

    def split_data(self):
        self.train_size = int(len(self.data) * .8)
        self.val_size = int(len(self.data) * .2)
        self.test_size = int(len(self.data) * .0)
        self.train = self.data.take(self.train_size)
        self.val = self.data.skip(self.train_size).take(self.val_size)
        self.test = self.data.skip(self.train_size + self.val_size).take(self.test_size)
        print(f"{bcolors.OKGREEN}spliting data succsesfuly{bcolors.ENDC}")

    def prefetching_data(self):
        self.train = self.train.prefetch(tf.data.AUTOTUNE)
        self.val = self.val.prefetch(tf.data.AUTOTUNE)
        self.test = self.test.prefetch(tf.data.AUTOTUNE)
        print(f"{bcolors.OKGREEN}prefetching data succsesfuly{bcolors.ENDC}")

    @staticmethod
    def make_small_Xception_model(input_shape, num_classes=2):
        inputs = keras.Input(shape=input_shape)

        x = tf.compat.v1.keras.layers.Rescaling(1.0 / 255)(inputs)
        x = Conv2D(128, 3, strides=2, padding="same")(x)
        x = tf.compat.v1.keras.layers.BatchNormalization()(x)
        x = Activation("relu")(x)

        previous_block_activision = x
        for size in [256, 512, 728]:
            x = Activation("relu")(x)
            x = layers.SeparableConv2D(size, 3, padding="same")(x)
            x = tf.compat.v1.keras.layers.BatchNormalization()(x)
            x = Activation("relu")(x)
            x = layers.SeparableConv2D(size, 3, padding="same")(x)
            x = tf.compat.v1.keras.layers.BatchNormalization()(x)
            x = MaxPooling2D(3, strides=2, padding="same")(x)
            # residual
            residual = Conv2D(size, 1, strides=2, padding="same")(previous_block_activision)
            x = layers.add([x, residual])
            previous_block_activision = x

        x = layers.SeparableConv2D(1024, 3, padding="same")(x)
        x = tf.compat.v1.keras.layers.BatchNormalization()(x)
        x = Activation("relu")(x)
        x = GlobalAveragePooling2D()(x)
        if num_classes == 2:
            activision = "sigmoid"
            units = 1
        else:
            activision = "softmax"
            units = num_classes
        x = Dropout(0.5)(x)
        outputs = Dense(units, activation=activision)(x)
        return keras.Model(inputs, outputs)

    def build_model(self, optimizer, model_type="s1"):
        print(f"model type : {model_type}")
        succsesful = False
        if model_type == "s1" or model_type == "s1a":
            self.model = Sequential()
            self.model.add(Conv2D(16, (3, 3), 1, activation='relu', input_shape=(256, 256, 3)))
            self.model.add(MaxPooling2D())
            self.model.add(Conv2D(32, (3, 3), 1, activation='relu'))
            self.model.add(MaxPooling2D())
            self.model.add(Conv2D(16, (3, 3), 1, activation='relu'))
            self.model.add(MaxPooling2D())
            self.model.add(Flatten())
            self.model.add(Dense(256, activation='relu'))
            self.model.add(Dense(1, activation='sigmoid'))
            succsesful = True

        elif model_type == "s2":
            self.model = Sequential()
            self.model.add(Conv2D(16, (3, 3), 1, activation='relu', input_shape=(256, 256, 3)))
            self.model.add(MaxPooling2D())
            self.model.add(Conv2D(32, (3, 3), 1, activation='relu'))
            self.model.add(MaxPooling2D())
            self.model.add(Conv2D(32, (3, 3), 1, activation='relu'))
            self.model.add(MaxPooling2D())
            self.model.add(Flatten())
            self.model.add(Dense(256, activation='relu'))
            self.model.add(Dense(1, activation='sigmoid'))
            succsesful = True

        elif model_type == "s3":
            self.model = Sequential()
            self.model.add(Conv2D(32, (3, 3), 1, activation='relu', input_shape=(256, 256, 3)))
            self.model.add(MaxPooling2D())
            self.model.add(Conv2D(32, (3, 3), 1, activation='relu'))
            self.model.add(MaxPooling2D())
            self.model.add(Conv2D(64, (3, 3), 1, activation='relu'))
            self.model.add(MaxPooling2D())
            self.model.add(Dropout(0.4))
            self.model.add(Flatten())
            self.model.add(Dense(128, activation='relu'))
            self.model.add(Dense(1, activation='sigmoid'))
            succsesful = True

        elif model_type == "m1":
            self.model = Sequential()
            self.model.add(Conv2D(32, (3, 3), 1, padding="same", activation='relu', input_shape=(256, 256, 3)))
            self.model.add(Conv2D(32, (3, 3), 1, activation='relu'))
            self.model.add(MaxPooling2D())
            self.model.add(Dropout(0.25))
            self.model.add(Conv2D(64, (3, 3), 1, padding="same", activation='relu'))
            self.model.add(Conv2D(64, (3, 3), 1, activation='relu'))
            self.model.add(MaxPooling2D())
            self.model.add(Dropout(0.25))
            self.model.add(Flatten())
            self.model.add(Dense(512, activation='relu'))
            self.model.add(Dropout(0.5))
            self.model.add(Dense(1, activation='sigmoid'))
            succsesful = True
        elif model_type == "x1":
            self.model = self.make_small_Xception_model(input_shape=(256, 256, 3), num_classes=2)
        else:
            print(f"{bcolors.FAIL}model {model_type} is undifinde\n"
                  f"it will defuat to s1 {bcolors.ENDC}")
            self.build_model(model_type="s1", optimizer=optimizer)
            succsesful = False

        if succsesful:
            print(self.model.summary())

        self.model.compile(optimizer=optimizer, loss=tf.losses.BinaryCrossentropy(), metrics=['accuracy'])

    @staticmethod
    def build_optimizer(learning_rate=0.00001, optimizer_type="adam"):
        opt = None
        if optimizer_type.lower() == "adam":
            opt = Adam(learning_rate=learning_rate)
        return opt

    def seting_logdir(self):
        current_dir = os.getcwd()
        parent_dir = os.path.dirname(current_dir)
        if self.logdir is None:
            if Path('new_folder').is_dir():
                self.logdir = "logs"
            else:
                path = os.path.join(parent_dir, "logs")
                os.mkdir(path)
                self.logdir = "logs"
        else:
            if Path(self.logdir).is_dir():
                pass
            else:
                path = os.path.join(parent_dir, self.logdir)
                os.mkdir(path)

    def train_model(self, epochs=20, model_type="s1", logdir=None, optimizer_type="adam", learning_rate=0.00001,
                    class_weight=None, prefetching=False, plot_model=True):
        if type(epochs) is not int:
            print(f"{bcolors.FAIL}epochs should be an int\n"
                  f"it will defualt to 20{bcolors.ENDC}")
            epochs = 20
        self.oom_avoider()
        self.remove_dogy_images()
        self.load_data()
        self.scale_data(model_type=model_type)
        self.augmanet_data(model_type=model_type)
        self.split_data()
        if prefetching:
            self.prefetching_data()
        self.logdir = logdir
        self.seting_logdir()
        self.optimizer = self.build_optimizer(optimizer_type=optimizer_type, learning_rate=learning_rate)
        self.build_model(model_type=model_type, optimizer=self.optimizer)
        if plot_model:
            tf.keras.utils.plot_model(self.model, show_shapes=True, show_layer_activations=True)
        self.tensorboard_callback = tf.keras.callbacks.TensorBoard(log_dir=self.logdir)
        self.hist = self.model.fit(self.train, epochs=epochs, validation_data=self.val,
                                   callbacks=[self.tensorboard_callback], class_weight=class_weight)
        self.plot_acc()
        self.plot_loss()

    def plot_loss(self):
        fig = plt.figure()
        plt.plot(self.hist.history['loss'], color='teal', label='loss')
        plt.plot(self.hist.history['val_loss'], color='orange', label='val_loss')
        fig.suptitle('Loss', fontsize=20)
        plt.legend(loc="upper left")
        plt.grid()
        plt.show()

    def plot_acc(self):
        fig = plt.figure()
        plt.plot(self.hist.history['accuracy'], color='teal', label='accuracy')
        plt.plot(self.hist.history['val_accuracy'], color='orange', label='val_accuracy')
        fig.suptitle('Accuracy', fontsize=20)
        plt.legend(loc="upper left")
        plt.grid()
        plt.show()

    def save_model(self, model_file_name=None):
        if model_file_name is None:
            model_file_name = self.name
        self.model.save(f"{model_file_name}.h5")

    def load_model(self, name="imageclassification_model"):
        self.model = load_model(f"{name}.h5")

    @staticmethod
    def oom_avoider():
        gpus = tf.config.experimental.list_physical_devices("GPU")
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)

    def predict_from_files_path(self, image_file_path):
        img = cv2.imread(image_file_path)
        resize = tf.image.resize(img, (256, 256))
        yhat = self.model.predict(np.expand_dims(resize / 255, 0))
        if yhat > 0.5:
            return self.first_class
        else:
            return self.second_class

    def predict_from_imshow(self, img):
        resize = tf.image.resize(img, (256, 256))
        yhat = self.model.predict(np.expand_dims(resize / 255, 0))
        if yhat > 0.5:
            return self.first_class
        else:
            return self.second_class

    def evaluate_model(self):
        self.pre = Precision()
        self.re = Recall()
        self.acc = BinaryAccuracy()
        for batch in self.test.as_numpy_iterator():
            X, y = batch
            yhat = self.model.predict(X)
            self.pre.update_state(y, yhat)
            self.re.update_state(y, yhat)
            self.acc.update_state(y, yhat)
        return [self.pre.result(), self.re.result(), self.acc.result()]

    def realtime_prediction(self):
        # Variables declarations
        frame_count = 0
        last = 0
        font = cv2.FONT_HERSHEY_TRIPLEX
        font_color = (255, 255, 255)
        vs = VideoStream(src=0).start()
        while True:
            frame = vs.read()
            frame_count += 1

            # Only run every 10 frames
            if frame_count % 10 == 0:
                prediction = self.predict_from_imshow(frame)
                # Change the text position depending on your camera resolution
                cv2.putText(frame, prediction, (20, 400), font, 1, font_color)

                if frame_count > 20:
                    fps = vs.stream.get(cv2.CAP_PROP_FPS)
                    fps_text = "fps: " + str(np.round(fps, 2))
                    cv2.putText(frame, fps_text, (460, 460), font, 1, font_color)

                cv2.imshow("Frame", frame)
                last += 1

                # if the 'q' key is pressed, stop the loop
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        # cleanup everything
        vs.stop()
        cv2.destroyAllWindows()
        print("Done")

    def realtime_face_prediction(self):
        detector = cv2.CascadeClassifier("haarcascade_frontalcatface.xml")
        camera = cv2.VideoCapture(0)
        # keep looping
        while True:
            # grab the current frame
            (grabbed, frame) = camera.read()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frameClone = frame.copy()
            rects = detector.detectMultiScale(gray, scaleFactor=1.1,
                                              minNeighbors=5, minSize=(10, 10),
                                              flags=cv2.CASCADE_SCALE_IMAGE)
            # loop over the face bounding boxes
            for (fX, fY, fW, fH) in rects:
                # extract the ROI of the face from the grayscale image,
                # resize it to a fixed 28x28 pixels, and then prepare the
                # ROI for classification via the CNN
                roi = frame[fY:fY + fH, fX:fX + fW]
                roi = cv2.resize(roi, (256, 256))
                roi = roi.astype("float") / 255.0
                roi = img_to_array(roi)
                roi = np.expand_dims(roi, axis=0)
                prediction = str(self.model.predict(roi))
                label = prediction
                cv2.putText(frameClone, label, (fX, fY - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)
                cv2.rectangle(frameClone, (fX, fY), (fX + fW, fY + fH),
                              (0, 0, 255), 2)
            # show our detected faces along with smiling/not smiling labels
            cv2.imshow("Face", frameClone)
            # if the 'q' key is pressed, stop the loop
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        # cleanup the camera and close any open windows
        camera.release()
        cv2.destroyAllWindows()
