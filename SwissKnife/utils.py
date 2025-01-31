"""
SIPEC
MARKUS MARKS
UTILITY FUNCTIONS
"""
import ast
import datetime
import os
import os.path
import pickle
import random
from distutils.version import LooseVersion
from glob import glob

import cv2
import numpy as np
import pandas as pd
import skimage
import tensorflow as tf
import tensorflow.keras as keras
from matplotlib import pyplot as plt
from scipy.ndimage import binary_dilation, center_of_mass
from skimage.filters import gaussian, threshold_minimum
from skimage.measure import regionprops
from skimage.transform import rescale
from sklearn.metrics import balanced_accuracy_score, classification_report, f1_score
from tensorflow.keras import backend as K
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tqdm import tqdm
# from tensorflow.keras.utils import multi_gpu_model

# TODO: remove unused code
def preprocess_imagenet(X):
    """TODO: Fill in description"""
    X = X.astype("float")
    # mean and std adjustments with imagenet weights
    X[:, :, :, 0] -= 0.485
    X[:, :, :, 0] /= 0.229
    X[:, :, :, 1] -= 0.456
    X[:, :, :, 1] /= 0.224
    X[:, :, :, 2] -= 0.406
    X[:, :, :, 2] /= 0.225
    X = X.astype("uint8")

    return X


# TODO: remove unused code
def mask_image_to_individuals(mask_image):
    """TODO: Fill in description"""
    mask = mask_image[:, :, 0]
    mask[mask == 255] = 0
    mask[mask > 0] = 1
    output = cv2.connectedComponents(mask.astype(np.uint8))
    mask_list = []
    for label in np.unique(output[1])[1:]:
        mask_list.append(mask == label)
    mask_list = np.array(mask_list)
    mask_list = np.moveaxis(mask_list, 0, 2)
    return mask_list


### pose estimation utils
def heatmaps_for_images(labels, img_shape, sigma=3, threshold=None):
    """TODO: Fill in description"""
    heatmaps = []
    for el in labels:
        maps = heatmaps_for_image_whole(
            img_shape=img_shape, labels=el, sigma=sigma, threshold=threshold
        )
        heatmaps.append(maps)
    heatmaps = np.asarray(heatmaps)

    return heatmaps.astype("float32")


def heatmaps_to_locs(y):
    """TODO: Fill in description"""
    locs = []
    for maps in y:
        map_locs = []
        for map_id in range(y.shape[-1]):
            map = maps[:, :, map_id]
            loc = np.where(map == map.max())
            map_locs.append([loc[1][0], loc[0][0]])
        locs.append(np.array(map_locs))

    y = np.array(locs)

    return y


def heatmap_mask(maps, mask):
    """TODO: Fill in description"""
    ret = False
    for mold in tqdm(maps):
        a = mold * mask
        if a.sum() > 10:
            return True
    return ret


# TODO: remove unused code
def heatmaps_for_image(labels, window=100, sigma=3):
    """TODO: Fill in description"""
    heatmaps = []
    for label in labels:
        heatmap = np.zeros((window, window))
        heatmap[int(label[1]), int(label[0])] = 1
        heatmap = gaussian(heatmap, sigma=sigma)
        heatmap[heatmap > 0.001] = 1
        heatmaps.append(heatmap)

    heatmaps = np.asarray(heatmaps)
    heatmaps = np.moveaxis(heatmaps, 0, 2)

    return heatmaps


def heatmaps_for_image_whole(labels, img_shape, sigma=3, threshold=None):
    """TODO: Fill in description"""
    heatmaps = []
    for label in labels:
        heatmap = np.zeros(img_shape)
        if label[1] > -1:
            heatmap[int(label[1]), int(label[0])] = 1
            heatmap = gaussian(heatmap, sigma=sigma)
            # threshold
            if threshold:
                heatmap[heatmap > threshold] = 1
            else:
                heatmap = heatmap / heatmap.max()
        heatmaps.append(heatmap)
    heatmaps = np.asarray(heatmaps)
    heatmaps = np.moveaxis(heatmaps, 0, 2)
    return heatmaps


# TODO: remove unused code
def keypoints_in_mask(mask, keypoints):
    """TODO: Fill in description"""
    for point in keypoints:
        keypoint = point.astype(int)

        res = mask[keypoint[1], keypoint[0]]
        if res is False:
            return False
    return True


def heatmap_to_scatter(heatmaps, threshold=0.6e-9):
    """TODO: Fill in description"""
    coords = []

    for idx in range(0, heatmaps.shape[-1]):
        heatmap = heatmaps[:, :, idx]
        # heatmap = gaussian(heatmap, sigma=2)
        val = max(heatmap.flatten())
        if val > threshold:
            _coord = np.where(heatmap == val)
            coords.append([_coord[1][0], _coord[0][0]])
        else:
            coords.append([0, 0])

    return np.asarray(coords)


def dilate_mask(mask, factor=20):
    """TODO: Fill in description"""
    new_mask = binary_dilation(mask, iterations=factor)

    return new_mask


# TODO: remove unused code
def bbox_mask(model, img, verbose=0):
    """TODO: Fill in description"""
    image, _, _, _, _ = utils.resize_image(
        img,
        # min_dim=config.IMAGE_MIN_DIM,
        # min_scale=config.IMAGE_MIN_SCALE,
        # max_dim=config.IMAGE_MAX_DIM,
        # mode=config.IMAGE_RESIZE_MODE)
        # TODO: nicer here
        min_dim=2048,
        max_dim=2048,
        mode="square",
    )
    if verbose:
        vid_results = model.detect([image], verbose=1)
    else:
        vid_results = model.detect([image], verbose=0)
    r = vid_results[0]

    return image, r["scores"], r["rois"], r["masks"]


### END Poseestimation utils


def masks_to_coords(masks):
    """TODO: Fill in description"""
    coords = []
    for i in range(masks.shape[-1]):
        coords.append(np.column_stack(np.where(masks[:, :, i] > 0)).astype("uint16"))
    return coords


def coords_to_masks(coords, dim=2048):
    """TODO: Fill in description"""
    masks = np.zeros((dim, dim, len(coords)), dtype="uint8")
    for coord_id, coord in enumerate(coords):
        for co in coord:
            masks[co[0], co[1], coord_id] = 1
    return masks


# TODO: Check this function
# TODO: remove unused code
def saveModel(model):
    """TODO: Fill in description"""
    json_model = model_tt.model.to_json()
    open("model_architecture.json", "w").write(json_model)
    model_tt.model.save_weights("model_weights.h5", overwrite=True)


# TODO: remove unused code
def clearMemory(model, backend):
    """TODO: Fill in description"""
    del model
    backend.clear_session()


# TODO: remove unused code
def fix_layers(network, with_backbone=True):
    """TODO: Fill in description"""
    for layer in network.layers:
        layer.trainable = True
        if with_backbone:
            if "layers" in dir(layer):
                for _layer in layer.layers:
                    _layer.trainable = True
    return network


# TODO: remove unused code
# helper class to keep track of results from different methods
class ResultsTracker:
    """write results as comma seperated lines in a single file"""

    def __init__(self, path=None):
        self.path = path

    def add_result(self, results):
        """TODO: Fill in description"""
        if os.path.exists(self.path):
            while not self.file_available():
                pass
        self.write_results(results)

    def write_results(self, results):
        """TODO: Fill in description"""
        for result in results:
            with open(self.path, "a") as hs:
                hs.write(result + "\n")

    def file_available(self):
        """TODO: Fill in description"""
        try:
            os.rename(self.path, self.path)
            print('Access on file "' + self.path + '" is available!')
            return 1
        except OSError as e:
            print('Access on file "' + self.path + '" is not available!')
            print(str(e))
            return 0


# TODO: include multi behavior
def load_vgg_labels(annotations, video_length, framerate_video, behavior=None):
    """TODO: Fill in description"""
    if isinstance(annotations, str):
        annotations = pd.read_csv(annotations, error_bad_lines=False, header=1)
    labels = ["none"] * video_length

    if "temporal_segment_start" in annotations.columns:
        for line in annotations.iterrows():
            start = int(line[1]["temporal_segment_start"] * framerate_video)
            end = int(line[1]["temporal_segment_end"] * framerate_video)
            if behavior is not None:
                label = behavior
            else:
                label = ast.literal_eval(line[1]["metadata"])["1"]
            labels[start:end] = [label] * (end - start)
    elif "temporal_coordinates" in annotations.columns:
        for line in annotations.iterrows():
            start = int(
                float(line[1]["temporal_coordinates"][1:-1].split(",")[0])
                * framerate_video
            )
            end = int(
                float(line[1]["temporal_coordinates"][1:-1].split(",")[1])
                * framerate_video
            )
            if behavior is not None:
                label = behavior
            else:
                label = ast.literal_eval(line[1]["metadata"])["1"]
            labels[start:end] = [label] * (end - start)
    else:
        raise NotImplementedError

    return labels


# TODO: remove unused code
def distance(x, y, x_prev, y_prev):
    """TODO: Fill in description"""
    return np.sqrt((x - x_prev) ** 2 + (y - y_prev) ** 2)


# TODO: remove unused code
def calculate_speed(distances):
    """TODO: Fill in description"""
    x = range(0, len(distances))
    y = distances
    dx = np.diff(x)
    dy = np.diff(y)
    d = dy / dx

    return d


# TODO: remove unused code
# crop png images for segmentation inputs
def crop_pngs():
    """TODO: Fill in description"""
    # TODO: Remove hardcoded paths
    basepath = "/media/nexus/storage1/swissknife_data/primate/segmentation_inputs/annotated_frames/"
    new_path = "/media/nexus/storage1/swissknife_data/primate/segmentation_inputs/annotated_frames_resized/"
    folders = ["train/", "val/"]
    for folder in folders:
        path = basepath + folder
        images = glob(path + "*.png")
        for image in images:
            helper = skimage.io.imread(image)
            # TODO: plt is not defined
            plt.figure(figsize=(20, 10))
            plt.imshow(helper)
            new_img = helper[:1024, :, :]
            filename = image.split(folder)[-1]
            skimage.io.imsave(new_path + folder + filename, new_img)


def rescale_img(mask, frame, mask_size=256):
    """TODO: Fill in description"""
    rectsize = [mask[3] - mask[1], mask[2] - mask[0]]

    rectsize = np.asarray(rectsize)
    scale = mask_size / rectsize.max()

    cutout = frame[mask[0] : mask[0] + rectsize[1], mask[1] : mask[1] + rectsize[0], :]

    img_help = rescale(cutout, scale, multichannel=True)
    padded_img = np.zeros((mask_size, mask_size, 3))

    padded_img[
        int(mask_size / 2 - img_help.shape[0] / 2) : int(
            mask_size / 2 + img_help.shape[0] / 2
        ),
        int(mask_size / 2 - img_help.shape[1] / 2) : int(
            mask_size / 2 + img_help.shape[1] / 2
        ),
        :,
    ] = img_help

    return padded_img


# TODO: make all of these part of segmentation/identification


def set_random_seed(random_seed):
    """This function sets Python and tensorflow random seeds"""
    os.environ["PYTHONHASHSEED"] = str(random_seed)
    random.seed(random_seed)
    tf.compat.v1.set_random_seed(random_seed)
    tf.compat.v1.random.set_random_seed(random_seed)


def detect_primate(_img, _model, classes, threshold):
    """TODO: Fill in description"""
    prediction = _model.predict(np.expand_dims(_img, axis=0))
    if prediction.max() > threshold:
        return classes[np.argmax(prediction)], prediction.max()
    else:
        return "None detected", prediction.max()


def masks_to_coms(masks):
    """calculate center of masses"""
    coms = []
    for idx in range(0, masks.shape[-1]):
        mask = masks[:, :, idx]
        com = center_of_mass(mask.astype("int"))
        coms.append(com)
    coms = np.asarray(coms)

    return coms


def apply_to_mask(mask, img, com, mask_size):
    """TODO: Fill in description"""
    masked_img = maskedImg(img, com, mask_size=mask_size)
    masked_mask = maskedImg(mask, com, mask_size=mask_size)

    return masked_img, masked_mask


def apply_all_masks(masks, coms, img, mask_size=128):
    """mask images"""
    masked_imgs = []
    masked_masks = []
    for idx, com in enumerate(coms):
        mask = masks[:, :, idx]
        masked_img, masked_mask = apply_to_mask(mask, img, com, mask_size=mask_size)
        masked_masks.append(masked_mask)
        masked_imgs.append(masked_img)

    return np.asarray(masked_imgs), np.asarray(masked_masks)


# functions for data processing

# TODO: remove unused code
### BEHAVIOR PREPROCESSING ###
def startend(df_entry, ms, df):
    """TODO: Fill in description"""
    start = float(df_entry["temporal_coordinates"][2:-2].split(",")[0]) / ms
    end = float(df_entry["temporal_coordinates"][2:-2].split(",")[1]) / ms
    label = df_entry["metadata"][2:-2].split(":")[-1][1:-1]
    length = float(end - start)

    return int(start), int(end), label, length


#### manual segmentation ###


# TODO: remove unused code
def extractCOM(image, threshold):
    """TODO: Fill in description"""
    try:
        try:
            threshold = threshold_minimum(image, nbins=256)
        except RuntimeError:
            threshold = threshold_minimum(image, nbins=768)
    except RuntimeError:
        threshold = threshold_minimum(image, nbins=1024)
    thresh = image > threshold
    labeled_foreground = (thresh).astype(int)
    properties = regionprops(labeled_foreground, thresh)
    center_of_mass = properties[0].centroid
    weighted_center_of_mass = properties[0].weighted_centroid

    return center_of_mass, weighted_center_of_mass

# TODO: remove unused code
# TODO: fixme / streamline
def extractCOM_only(image):
    """TODO: Fill in description"""
    properties = regionprops(image)
    center_of_mass = properties[0].centroid
    weighted_center_of_mass = properties[0].weighted_centroid

    return center_of_mass, weighted_center_of_mass


def mask_to_original_image(orig_shape, mask, center_of_mass, mask_size):
    """TODO: Fill in description"""

    img = np.zeros((orig_shape, orig_shape))


    x_min = np.max([0, int(center_of_mass[0] - mask_size//2)])
    x_max = np.min([img.shape[0], int(center_of_mass[0] + mask_size//2)])
    y_min = np.max([0, int(center_of_mass[1] - mask_size//2)])
    y_max = np.min([img.shape[0], int(center_of_mass[1] + mask_size//2)])


    x_dim = x_max - x_min
    y_dim = y_max - y_min

    if int(center_of_mass[0] + mask_size) > img.shape[0]:
        mask = mask[-x_dim:, :]
    if int(center_of_mass[1] + mask_size) > img.shape[1]:
        mask = mask[:, -y_dim:]
    if 0 > int(center_of_mass[0] - mask_size):
        mask = mask[:x_dim, :]
    if 0 > int(center_of_mass[1] - mask_size):
        mask = mask[:, :y_dim]

    img[
        x_min:x_max,
        y_min:y_max,
    ] = mask

    return img


def maskedImg(
    img,
    center_of_mass,
    mask_size=74,
):
    """TODO: Fill in description"""
    if len(img.shape) == 2:
        ret = np.zeros((int(mask_size * 2), int(mask_size * 2)))
    else:
        ret = np.zeros((int(mask_size * 2), int(mask_size * 2), img.shape[-1]))

    cutout = img[
        np.max([0, int(center_of_mass[0] - mask_size)]) : np.min(
            [img.shape[0], int(center_of_mass[0] + mask_size)]
        ),
        np.max([0, int(center_of_mass[1] - mask_size)]) : np.min(
            [img.shape[0], int(center_of_mass[1] + mask_size)]
        ),
    ]

    ret[
        ret.shape[0] - int(cutout.shape[0]) : ret.shape[0] + int(cutout.shape[0]),
        ret.shape[1] - int(cutout.shape[1]) : ret.shape[1] + int(cutout.shape[1]),
    ] = cutout

    return ret


### DL Utils
# TODO: own file for DL utils

# TODO: remove unused code
def plotHistory(history, measure):
    """This function plots the 'measure/metric' as a function of epochs"""
    plt.plot(history.history[measure])
    plt.plot(history.history["val_" + measure])
    plt.title("model" + measure)
    plt.ylabel(measure)
    plt.xlabel("epoch")
    plt.legend(["train", "test"], loc="upper left")
    plt.show()


def categorical_focal_loss(gamma=2.0, alpha=0.25):
    """
    Implementation of Focal Loss from the paper in multiclass classification
    Formula:
        loss = -alpha*((1-p)^gamma)*log(p)
    Parameters:
        alpha -- the same as wighting factor in balanced cross entropy
        gamma -- focusing parameter for modulating factor (1-p)
    Default value:
        gamma -- 2.0 as mentioned in the paper
        alpha -- 0.25 as mentioned in the paper
    """

    def focal_loss(y_true, y_pred):
        # Define epsilon so that the backpropagation will not result in NaN
        # for 0 divisor case

        y_true = tf.cast(y_true, tf.float32)
        y_pred = tf.cast(y_pred, tf.float32)
        epsilon = K.epsilon()
        # Add the epsilon to prediction value
        # y_pred = y_pred + epsilon
        # Clip the prediction value
        y_pred = K.clip(y_pred, epsilon, 1.0 - epsilon)
        # Calculate cross entropy
        cross_entropy = -y_true * K.log(y_pred)
        # Calculate weight that consists of  modulating factor and weighting factor
        weight = alpha * y_true * K.pow((1 - y_pred), gamma)
        # Calculate focal loss
        loss = weight * cross_entropy
        # Sum the losses in mini_batch
        loss = K.sum(loss, axis=1)
        return loss

    return focal_loss


def f1(y_true, y_pred):
    """TODO: Fill in description"""
    y_true = K.cast(y_true, "float")

    #     y_pred = K.round(y_pred)

    y_pred = K.cast(K.greater(K.cast(y_pred, "float"), 0.01), "float")

    tp = K.sum(K.cast(y_true * y_pred, "float"), axis=0)
    # tn = K.sum(K.cast((1-y_true)*(1-y_pred), 'float'), axis=0)
    fp = K.sum(K.cast((1 - y_true) * y_pred, "float"), axis=0)
    fn = K.sum(K.cast(y_true * (1 - y_pred), "float"), axis=0)

    p = tp / (tp + fp + K.epsilon())
    r = tp / (tp + fn + K.epsilon())

    f1 = 2 * p * r / (p + r + K.epsilon())
    f1 = tf.compat.v1.where(tf.math.is_nan(f1), tf.zeros_like(f1), f1)
    return K.mean(f1)


# TODO: remove unused code
def f1_loss(y_true, y_pred):
    """TODO: Fill in description"""
    tp = K.sum(K.cast(y_true * y_pred, "float"), axis=0)
    tn = K.sum(K.cast((1 - y_true) * (1 - y_pred), "float"), axis=0)
    fp = K.sum(K.cast((1 - y_true) * y_pred, "float"), axis=0)
    fn = K.sum(K.cast(y_true * (1 - y_pred), "float"), axis=0)

    p = tp / (tp + fp + K.epsilon())
    r = tp / (tp + fn + K.epsilon())

    f1 = 2 * p * r / (p + r + K.epsilon())
    f1 = tf.compat.v1.where(tf.math.is_nan(f1), tf.zeros_like(f1), f1)
    return 1 - K.mean(f1)


# TODO: remove unused code
def balanced_acc(y_true, y_pred):
    """TODO: Fill in description"""
    with sess.as_default():
        return balanced_accuracy_score(y_true.eval(), y_pred.eval())


class Metrics(tf.keras.callbacks.Callback):
    """TODO: Fill in description"""

    def __init__(self, validation_data = None):
        self.validation_data = validation_data

    def setModel(self, model):
        self.model = model

    def on_train_begin(self, logs={}):
        self._data = []

    def on_epoch_end(self, batch, logs={}):
        X_val, y_val = self.validation_data[0], self.validation_data[1]
        y_val = np.argmax(y_val, axis=-1)

        # old
        y_predict = self.model.predict(X_val)
        y_predict = np.argmax(y_predict, axis=-1).astype(int)
        print(classification_report(y_val, y_predict))

        self._data.append(
            {
                "val_balanced_acc": balanced_accuracy_score(y_val, y_predict),
                "val_sklearn_f1": f1_score(y_val, y_predict, average="macro"),
            }
        )
        print("val_balanced_acc ::: " + str(balanced_accuracy_score(y_val, y_predict)))
        print("val_sklearn_f1 ::: " + str(f1_score(y_val, y_predict, average="macro")))
        return

    def get_data(self):
        return self._data


# TODO: maybe somewhere else?
def get_optimizer(optim_name, lr=0.01):
    """TODO: Fill in description"""
    optim = None
    if optim_name == "adam":
        optim = keras.optimizers.Adam(lr=lr, clipnorm=0.5)
    if optim_name == "sgd":
        optim = keras.optimizers.SGD(lr=lr, clipnorm=0.5, momentum=0.9)
    if optim_name == "rmsprop":
        optim = keras.optimizers.RMSprop(lr=lr)
    return optim


##callbacks


def callbacks_tf_logging(path="./logs/"):
    logdir = os.path.join(path, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    tf_callback = get_tensorbaord_callback(logdir)
    return tf_callback


def get_tensorbaord_callback(path="./logs"):
    # Tensorflow board
    tensorboard_callback = keras.callbacks.TensorBoard(
        log_dir=path, histogram_freq=0, write_graph=True, write_images=True
    )
    return tensorboard_callback


def callbacks_learningRate_plateau():
    CB_lr = keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", min_delta=0.0001, verbose=True, patience=8, min_lr=1e-7
    )

    CB_es = keras.callbacks.EarlyStopping(
        monitor="val_loss",
        min_delta=0.0001,
        patience=8,
        mode="min",
        restore_best_weights=True,
    )

    return CB_es, CB_lr


def get_callbacks(min_lr=1e-7, factor=0.1, patience=8, min_delta=0.0001, reduce=True):
    # import tensorflow.keras as keras

    CB_lr = ReduceLROnPlateau(
        monitor="val_loss",
        min_delta=min_delta,
        verbose=True,
        patience=patience,
        min_lr=min_lr,
        factor=factor,
    )

    CB_es = EarlyStopping(
        monitor="val_loss",
        min_delta=min_delta,
        patience=8,
        mode="min",
        restore_best_weights=True,
    )

    if reduce:
        return CB_es, CB_lr
    else:
        return CB_es


def train_model(
    model,
    optimizer,
    epochs,
    batch_size,
    dataloader,
    callbacks=None,
    class_weights=None,
    loss="crossentropy",
    augmentation=None,
    num_gpus=1,
    multi_workers=False,
    num_workers=1,
    sequential=False,
):
    if num_gpus > 1:
        # This would not work any longer. Update if parallelization over multiple GPUs is desired
        model = multi_gpu_model(model, gpus=num_gpus, cpu_merge=True)
    if loss == "crossentropy":
        # TODO: integrate number of GPUs in config
        model.compile(
            loss="categorical_crossentropy",
            optimizer=optimizer,
            metrics=["categorical_crossentropy", "categorical_accuracy"],
        )
    elif loss == "focal_loss":
        model.compile(
            # baseline is gamma 2, low is 1 , high is 5
            loss=categorical_focal_loss(gamma=5.0, alpha=0.5),
            optimizer=optimizer,
            metrics=["categorical_crossentropy", "categorical_accuracy", f1],
        )
    else:
        raise NotImplementedError

    print(model.summary())

    if dataloader.config["use_generator"]:
        training_history = model.fit(
            dataloader.training_generator,
            epochs=epochs,
            # batch_size=batch_size,
            # steps_per_epoch=int(len(dataloader.x_train)/batch_size),
            validation_data=dataloader.validation_generator,
            # validation_data=(x_test, y_test),
            callbacks=callbacks,
            # shuffle=True,
            # use_multiprocessing=False,
            # steps_per_epoch=50,
            # workers=num_workers,
        )
    else:

        if augmentation:
            image_gen = ImageDataGenerator(
                horizontal_flip=True,
                vertical_flip=True,
                preprocessing_function=augmentation.augment_image,
            )

            try:
                batch_gen = image_gen.flow(
                    dataloader.x_train,
                    dataloader.y_train,
                    batch_size=batch_size,
                    shuffle=True,
                    # TODO: implement here
                    # TODO: fix seed globallly
                    #     sample_weight=train_sample_weights,
                    # TODO: check if global seed works here
                    # seed=42,
                )
            except ValueError:
                batch_gen = image_gen.flow(
                    dataloader.x_train,
                    dataloader.y_train,
                    batch_size=batch_size,
                    shuffle=True,
                    # TODO: implement here
                    # TODO: fix seed globallly
                    #     sample_weight=train_sample_weights,
                    # seed=42,
                )
            # TODO: implement me
            # if balanced:
            # training_generator, steps_per_epoch = balanced_batch_generator(x_train, y_train,
            #                                                                sampler=RandomOverSampler(),
            #                                                                batch_size=32,
            #                                                                random_state=42)

            if class_weights is not None:
                training_history = model.fit_generator(
                    batch_gen,
                    epochs=epochs,
                    steps_per_epoch=len(dataloader.x_train[0]),
                    validation_data=(dataloader.x_test, dataloader.y_test),
                    callbacks=callbacks,
                    class_weight=class_weights,
                    use_multiprocessing=multi_workers,
                    workers=num_workers,
                )
            else:
                training_history = model.fit_generator(
                    batch_gen,
                    epochs=epochs,
                    # TODO: check here, also multiprocessing
                    steps_per_epoch=len(dataloader.x_train[0]),
                    validation_data=(dataloader.x_test, dataloader.y_test),
                    callbacks=callbacks,
                    use_multiprocessing=multi_workers,
                    workers=num_workers,
                )

        else:
            if class_weights is not None:
                if sequential:
                    training_history = model.fit(
                        dataloader.x_train_recurrent,
                        dataloader.y_train_recurrent,
                        epochs=epochs,
                        batch_size=batch_size,
                        validation_data=(
                            dataloader.x_test_recurrent,
                            dataloader.y_test_recurrent,
                        ),
                        callbacks=callbacks,
                        shuffle=True,
                        use_multiprocessing=multi_workers,
                        workers=num_workers,
                        class_weight=class_weights,
                    )
                else:
                    training_history = model.fit(
                        dataloader.x_train,
                        dataloader.y_train,
                        epochs=epochs,
                        batch_size=batch_size,
                        validation_data=(dataloader.x_test, dataloader.y_test),
                        callbacks=callbacks,
                        shuffle=True,
                        use_multiprocessing=multi_workers,
                        workers=num_workers,
                        class_weight=class_weights,
                    )
            else:
                if sequential:
                    training_history = model.fit(
                        dataloader.x_train_recurrent,
                        dataloader.y_train_recurrent,
                        epochs=epochs,
                        batch_size=batch_size,
                        validation_data=(
                            dataloader.x_test_recurrent,
                            dataloader.y_test_recurrent,
                        ),
                        callbacks=callbacks,
                        shuffle=True,
                        use_multiprocessing=multi_workers,
                        workers=num_workers,
                    )
                else:
                    training_history = model.fit(
                        dataloader.x_train,
                        dataloader.y_train,
                        epochs=epochs,
                        batch_size=batch_size,
                        validation_data=(dataloader.x_test, dataloader.y_test),
                        callbacks=callbacks,
                        shuffle=True,
                        use_multiprocessing=multi_workers,
                        workers=num_workers,
                    )

    return model, training_history


def eval_model(
    model,
    data,
    results_dict,
    results_array,
    filename,
    dataloader,
    model_name="",
):
    true_confidence = model.predict(data)
    true_numerical = np.argmax(true_confidence, axis=-1).astype(int)
    # TODO: also save certainty

    true_behavior = dataloader.decode_labels(true_numerical)

    true_numerical = np.expand_dims(true_numerical, axis=-1)
    true_behavior = np.expand_dims(true_behavior, axis=-1)

    true = np.hstack([true_confidence, true_numerical, true_behavior])

    # TODO: generate automatically
    res = results_dict.copy()
    res[model_name + filename] = true

    res_array = results_array.copy()
    for el in true:
        res_array.append(np.hstack([model_name, filename, el]))
    return res, res_array


def save_dict(filename, dict):
    """This function dumps a dict using the pickle library"""
    with open(filename, "wb") as handle:
        pickle.dump(dict, handle, protocol=pickle.HIGHEST_PROTOCOL)


def load_dict(filename):
    """This function loads a pickled dict object"""
    with open(filename, "rb") as handle:
        file = pickle.load(handle)
    return file


def check_directory(directory):
    """Creates a folder if it does not exist and raises an exception if it exists"""
    if not os.path.exists(directory):
        print("Creating directory {}".format(directory))
        os.makedirs(directory)
    else:
        raise ValueError(
            "Raising value exception as the experiment/directory {} already exists".format(
                directory
            )
        )


# TODO: remove unused code
def get_ax(rows=1, cols=1, size=8):
    """Return a Matplotlib Axes array to be used in
    all visualizations in the notebook. Provide a
    central point to control graph sizes.

    Change the default size attribute to control the size
    of rendered images
    """
    _, ax = plt.subplots(rows, cols, figsize=(size * cols, size * rows))
    return ax


# TODO: Potential duplicate function, see function check_directory(:
def check_folder(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


### set gpu backend
def setGPU_growth():
    physical_devices = tf.config.experimental.list_physical_devices("GPU")
    print(physical_devices)
    for device in physical_devices:
        tf.config.experimental.set_memory_growth(device, True)
    # session = tf.Session(config=config)
    # TODO: Replace the following by tf2 equivalent
    ##backend.tensorflow_backend.set_session(tf.Session(config=config))


def setGPU(gpu_name, growth=True):
    # os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"  # see issue #152
    # os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_name)
    tf.config.set_visible_devices(
        tf.config.list_physical_devices("GPU")[int(gpu_name)], "GPU"
    )
    if growth:
        setGPU_growth()
    pass


def pathForFile(paths, filename):
    if "labels" in paths[0]:
        filename = filename + "_"
    else:
        filename = filename + "."
    for path in paths:
        if filename in path:
            return path
    return "none"


def loadVideo(path, num_frames=None, greyscale=True):
    """load the video"""
    reader = cv2.VideoCapture(path)
    if not reader.isOpened():
        raise RuntimeError(f"Could not open video: {path}")

    width = int(reader.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(reader.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(reader.get(cv2.CAP_PROP_FRAME_COUNT)) if num_frames is None else num_frames
    channels = 1 if greyscale else 3
    frames = np.empty((frame_count,height,width,channels))

    for fidx in range(frame_count):
        result = reader.read()
        assert result[0]
        frames[fidx,:,:,:] = result[1]
    return frames

def load_config(path):
    params = {}
    with open(path) as f:
        for line in f.readlines():
            if "\n" in line:
                line = line.split("\n")[0]
            try:
                params[line.split(" = ")[0]] = int(line.split(" = ")[1])
            except ValueError:
                try:
                    params[line.split(" = ")[0]] = float(line.split(" = ")[1])
                except ValueError:
                    if "," in str(line.split(" = ")[1]):
                        if "." in line.split(" = ")[1]:
                            help = line.split(" = ")[1].split(",")
                            entries = [float(el) for el in help]
                            params[line.split(" = ")[0]] = entries
                        else:
                            help = line.split(" = ")[1].split(",")
                            entries = [int(el) for el in help]
                            params[line.split(" = ")[0]] = entries
                    else:
                        if str(line.split(" = ")[1]) == "None":
                            params[line.split(" = ")[0]] = None
                        else:
                            params[line.split(" = ")[0]] = str(line.split(" = ")[1])
    return params


# adapted from maskrcnn
def resize(
    image,
    output_shape,
    order=1,
    mode="constant",
    cval=0,
    clip=True,
    preserve_range=False,
    anti_aliasing=False,
    anti_aliasing_sigma=None,
):
    """A wrapper for Scikit-Image resize().

    Scikit-Image generates warnings on every call to resize() if it doesn't
    receive the right parameters. The right parameters depend on the version
    of skimage. This solves the problem by using different parameters per
    version. And it provides a central place to control resizing defaults.
    """
    if LooseVersion(skimage.__version__) >= LooseVersion("0.14"):
        # New in 0.14: anti_aliasing. Default it to False for backward
        # compatibility with skimage 0.13.
        return skimage.transform.resize(
            image,
            output_shape,
            order=order,
            mode=mode,
            cval=cval,
            clip=clip,
            preserve_range=preserve_range,
            anti_aliasing=anti_aliasing,
            anti_aliasing_sigma=anti_aliasing_sigma,
        )
    else:
        return skimage.transform.resize(
            image,
            output_shape,
            order=order,
            mode=mode,
            cval=cval,
            clip=clip,
            preserve_range=preserve_range,
        )


def resize_image(image, min_dim=None, max_dim=None, min_scale=None, mode="square"):
    # Keep track of image dtype and return results in the same dtype
    image_dtype = image.dtype
    # Default window (y1, x1, y2, x2) and default scale == 1.
    h, w = image.shape[:2]
    window = (0, 0, h, w)
    scale = 1
    padding = [(0, 0), (0, 0), (0, 0)]
    crop = None

    if mode == "none":
        return image, window, scale, padding, crop

    # Scale?
    if min_dim:
        # Scale up but not down
        scale = max(1, min_dim / min(h, w))
    if min_scale and scale < min_scale:
        scale = min_scale

    # Does it exceed max dim?
    if max_dim and mode == "square":
        image_max = max(h, w)
        if round(image_max * scale) > max_dim:
            scale = max_dim / image_max

    # Resize image using bilinear interpolation
    if scale != 1:
        image = resize(image, (round(h * scale), round(w * scale)), preserve_range=True)

    # Need padding or cropping?
    if mode == "square":
        # Get new height and width
        h, w = image.shape[:2]
        top_pad = (max_dim - h) // 2
        bottom_pad = max_dim - h - top_pad
        left_pad = (max_dim - w) // 2
        right_pad = max_dim - w - left_pad
        padding = [(top_pad, bottom_pad), (left_pad, right_pad), (0, 0)]
        image = np.pad(image, padding, mode="constant", constant_values=0)
        window = (top_pad, left_pad, h + top_pad, w + left_pad)
    elif mode == "pad64":
        h, w = image.shape[:2]
        # Both sides must be divisible by 64
        assert min_dim % 64 == 0, "Minimum dimension must be a multiple of 64"
        # Height
        if h % 64 > 0:
            max_h = h - (h % 64) + 64
            top_pad = (max_h - h) // 2
            bottom_pad = max_h - h - top_pad
        else:
            top_pad = bottom_pad = 0
        # Width
        if w % 64 > 0:
            max_w = w - (w % 64) + 64
            left_pad = (max_w - w) // 2
            right_pad = max_w - w - left_pad
        else:
            left_pad = right_pad = 0
        padding = [(top_pad, bottom_pad), (left_pad, right_pad), (0, 0)]
        image = np.pad(image, padding, mode="constant", constant_values=0)
        window = (top_pad, left_pad, h + top_pad, w + left_pad)
    elif mode == "crop":
        # Pick a random crop
        h, w = image.shape[:2]
        y = random.randint(0, (h - min_dim))
        x = random.randint(0, (w - min_dim))
        crop = (y, x, min_dim, min_dim)
        image = image[y : y + min_dim, x : x + min_dim]
        window = (0, 0, min_dim, min_dim)
    else:
        raise Exception("Mode {} not supported".format(mode))
    return image.astype(image_dtype), window, scale, padding, crop
