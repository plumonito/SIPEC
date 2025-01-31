# SIPEC
# MARKUS MARKS
# IDENTIFICATION

import sys
sys.path.append("../")
import json
import os
import random
import sys

from joblib import Parallel, delayed

from argparse import ArgumentParser
import imageio
import numpy as np
from tensorflow.keras import backend as K
from skimage.transform import rescale
import tensorflow as tf
from datetime import datetime

from SwissKnife.augmentations import primate_identification, mouse_identification
from SwissKnife.architectures import idtracker_ai
from SwissKnife.utils import (
    Metrics,
    setGPU,
    get_callbacks,
    check_directory,
    set_random_seed,
    load_config,
    loadVideo,
)
from SwissKnife.dataprep import (
    get_primate_identification_data,
    generate_individual_mouse_data,
)
from SwissKnife.segmentation import mold_image
from SwissKnife.dataloader import Dataloader
from SwissKnife.model import Model
from sklearn import metrics
from SwissKnife.dataprep import get_primate_paths


def evaluate_on_data(
    species, network, video=None, config=None, exclude_hard=False, masking=False
):
    if species == "mouse_crossday":
        # x_train, y_train, x_test, y_test = get_individual_mouse_data()

        x_train, y_train, x_test, y_test = generate_individual_mouse_data(
            animal_lim=8, cv_folds=5, fold=0, day=1, masking=masking
        )

        dataloader = Dataloader(
            x_train, y_train, x_test, y_test, config
        )

        # FIXME: remove?
        dataloader.change_dtype()

        # preproc labels
        print("encoding")
        dataloader.encode_labels()

        dataloader.expand_dims()

        dataloader.create_recurrent_data()
        dataloader.create_flattened_data()

        our_model = Model()
        our_model.load_recognition_model(network)
        res = our_model.predict(dataloader.x_test)

        metric = metrics.balanced_accuracy_score(
            # res, np.argmax(dataloader.y_test, axis=-1)
            res,
            dataloader.y_test,
        )
        print("Result", str(metric))

    if species == "primate":

        (
            video_train,
            classes,
            idresults_base,
            fnames_base,
            vid_basepath,
            video_1,
        ) = get_primate_paths()

        print(video_train)
        print("preparing data")
        X, y, vidlist = get_primate_identification_data(scaled=True)
        num_classes = 4

        print("before ,", str(len(X[0])))

        if exclude_hard:
            import pickle

            hard_list = "/media/nexus/storage5/swissknife_data/primate/identification_inputs/hard_list.pkl"
            with open(hard_list, "rb") as handle:
                excludes = pickle.load(handle)
            print(excludes)
            X_new = []
            y_new = []
            for vid_idx, elements in enumerate(excludes):
                X[vid_idx] = X[vid_idx][elements]
                y[vid_idx] = y[vid_idx][elements]

        print("after ,", str(len(X[0])))

        results = []
        videos = np.unique(vidlist)
        print(video)
        print(videos)
        idxs_list = []
        for vidname in videos:
            if video not in vidname:
                continue
            x_train = []
            y_train = []
            x_test = []
            y_test = []
            for idx, el in enumerate(vidlist):
                if vidname == el:
                    x_test.append(X[idx])
                    y_test.append(y[idx])
                    idxs_list.append(len(y[idx]))
                else:
                    x_train.append(X[idx])
                    y_train.append(y[idx])
            x_train = np.vstack(x_train)
            y_train = np.hstack(y_train)
            x_test = np.vstack(x_test)
            y_test = np.hstack(y_test)

            dataloader = Dataloader(
                x_train[:, 4, :, :, :],
                y_train,
                x_test[:, 4, :, :, :],
                y_test,
            )

            dataloader.categorize_data(num_classes=num_classes)
            print("data preparation done")

            our_model = Model()
            our_model.load_recognition_model(network)
            res = our_model.predict(dataloader.x_test)
            results.append(
                [
                    "SIPEC_recognition",
                    vidname,
                    metrics.accuracy_score(res, np.argmax(dataloader.y_test, axis=-1)),
                    metrics.f1_score(
                        res, np.argmax(dataloader.y_test, axis=-1), average="macro"
                    ),
                ]
            )
            print(metrics.confusion_matrix(res, np.argmax(dataloader.y_test, axis=-1)))
            print("Mismatches")
            print(vidname)
            print(len(dataloader.x_test))
            equal = res == np.argmax(dataloader.y_test, axis=-1)
            print(np.where(equal == 0))

        print("FINAL results")
        print(results)


def train_on_data(
    species,
    network,
    config,
    results_sink,
    dataloader=None,
    video=None,
    fraction=None,
    cv_folds=None,
    fold=None,
    masking=False,
):
    results = []

    if species == "primate" and dataloader is None:
        print("preparing data")
        X, y, vidlist = get_primate_identification_data(scaled=True)
        print(vidlist)
        results = []
        _results_sink = results_sink

        results_sink = _results_sink + video + "/"
        check_directory(results_sink)
        num_classes = 4

        x_train = []
        y_train = []
        x_test = []
        y_test = []
        for idx, el in enumerate(vidlist):
            if video == el:
                x_test.append(X[idx])
                y_test.append(y[idx])
            else:
                x_train.append(X[idx])
                y_train.append(y[idx])
        x_train = np.vstack(x_train)
        y_train = np.hstack(y_train)
        x_test = np.vstack(x_test)
        y_test = np.hstack(y_test)

        dataloader = Dataloader(
            x_train[:, 4, :, :, :],
            y_train,
            x_test[:, 4, :, :, :],
            y_test,
            config=config,
        )

        dataloader.x_train_recurrent = x_train
        dataloader.y_train_recurrent = y_train
        dataloader.x_test_recurrent = x_test
        dataloader.y_test_recurrent = y_test

        # TODO: doesn't work here
        dataloader.downscale_frames()
        dataloader.change_dtype()

        print("data preparation done")

    elif species == "mouse" and dataloader is None:
        num_classes = 8

        # x_train, y_train, x_test, y_test = get_individual_mouse_data()

        x_train, y_train, x_test, y_test = generate_individual_mouse_data(
            animal_lim=num_classes, cv_folds=cv_folds, fold=fold, masking=masking
        )

        dataloader = Dataloader(x_train, y_train, x_test, y_test, config=config)

        # FIXME: remove?
        dataloader.change_dtype()

        # dataloader.normalize_data()

        # preproc labels
        print("encoding")
        dataloader.encode_labels()

        dataloader.expand_dims()

        video = "mouse"

        # dataloader.undersample_data()

    if network == "ours" or network == "both":
        our_model = Model()

        class_weights = None
        if config["use_class_weights"]:
            from sklearn.utils import class_weight

            class_weights = class_weight.compute_class_weight(
                "balanced", np.unique(y_train), y_train
            )
            our_model.set_class_weight(class_weights)

        if config["undersample"]:
            print("undersampling")
            dataloader.undersample_data()

        if config["is_test"]:
            # dataloader.undersample_data()
            dataloader.decimate_labels(percentage=0.33)

        dataloader.categorize_data(num_classes=dataloader.get_num_classes())

        # todo: change pos
        if species == "mouse" and dataloader is None:
            dataloader.create_recurrent_data()
            dataloader.create_flattened_data()

        if fraction is not None:
            dataloader.decimate_labels(percentage=fraction)
            print("Training data recuded to: ", str(len(dataloader.x_train)))

        # chose recognition model
        our_model.set_recognition_model(
            architecture=config["recognition_backbone"],
            input_shape=dataloader.get_input_shape(),
            num_classes=dataloader.get_num_classes(),
        )

        # set optimizer
        our_model.set_optimizer(
            config["recognition_model_optimizer"],
            lr=config["recognition_model_lr"],
        )

        ## Define callbacks
        # use lr scheduler
        if config["recognition_model_use_scheduler"]:
            our_model.scheduler_lr = config["recognition_model_scheduler_lr"]
            our_model.scheduler_factor = config["recognition_model_scheduler_factor"]
            our_model.set_lr_scheduler()
        else:
            # use standard training callback
            CB_es, CB_lr = get_callbacks()
            our_model.add_callbacks([CB_es, CB_lr])

        # add sklearn metrics for tracking in training
        my_metrics = Metrics(validation_data=(dataloader.x_test, dataloader.y_test))
        my_metrics.setModel(our_model.recognition_model)
        our_model.add_callbacks([my_metrics])

        if species == "primate":
            augmentation = primate_identification(level=config["augmentation_level"])
        elif species == "mouse":
            augmentation = mouse_identification(level=config["augmentation_level"])
        else:
            # TODO: add more species/generic augmentation
            augmentation = primate_identification(level=config["augmentation_level"])
        if config["recognition_model_augmentation"]:
            our_model.set_augmentation(augmentation)

        our_model.recognition_model_batch_size = config["recognition_model_batch_size"]
        our_model.recognition_model_epochs = config["recognition_model_epochs"]

        if config["train_recognition_model"]:
            # start training of recognition network
            our_model.recognition_model_loss = config["recognition_model_loss"]
            our_model.train_recognition_network(dataloader=dataloader)
            our_model.recognition_model.save(
                results_sink + "IDnet_"  + "_recognitionNet" + ".h5"
            )

            res = our_model.predict(dataloader.x_test)
            res = np.argmax(res[0], axis=-1)
            results.append(
                [
                    "SIPEC_recognition",
                    video,
                    fraction,
                    metrics.balanced_accuracy_score(
                        res, np.argmax(dataloader.y_test, axis=-1)
                    ),
                    metrics.f1_score(
                        res,
                        np.argmax(dataloader.y_test, axis=-1),
                        average="macro",
                    ),
                ]
            )
            print(results[-1])

        if config["train_sequential_model"]:
            our_model.fix_recognition_layers()
            our_model.remove_classification_layers()

            our_model.sequential_model_loss = config["sequential_model_loss"]

            # TODO: prettify me!
            if species == "primate":
                dataloader.categorize_data(num_classes=num_classes, recurrent=True)

            print("input shape", dataloader.get_input_shape())

            our_model.set_sequential_model(
                architecture=config["sequential_backbone"],
                input_shape=dataloader.get_input_shape(recurrent=True),
                num_classes=num_classes,
            )
            my_metrics.setModel(our_model.sequential_model)
            my_metrics.validation_data = (
                dataloader.x_test_recurrent,
                dataloader.y_test_recurrent,
            )
            our_model.add_callbacks([my_metrics])
            our_model.set_optimizer(
                config["sequential_model_optimizer"],
                lr=config["sequential_model_lr"],
            )
            if config["sequential_model_use_scheduler"]:
                our_model.scheduler_lr = config["sequential_model_scheduler_lr"]
                our_model.scheduler_factor = config["sequential_model_scheduler_factor"]
                our_model.set_lr_scheduler()

            our_model.sequential_model_epochs = config["sequential_model_epochs"]
            our_model.sequential_model_batch_size = config[
                "sequential_model_batch_size"
            ]

            CB_es, CB_lr = get_callbacks()
            CB_train = [CB_lr, CB_es]
            # our_model.add_callbacks(CB_train)

            our_model.train_sequential_network(dataloader=dataloader)
            print(our_model.sequential_model.summary())

            res = our_model.predict_sequential(dataloader.x_test_recurrent)
            res = np.argmax(res[0], axis=-1)
            results.append(
                [
                    "SIPEC_sequential",
                    video,
                    fraction,
                    metrics.balanced_accuracy_score(
                        res, np.argmax(dataloader.y_test_recurrent, axis=-1)
                    ),
                    metrics.f1_score(
                        res,
                        np.argmax(dataloader.y_test_recurrent, axis=-1),
                        average="macro",
                    ),
                ]
            )
            print(results[-1])
            # our_model.sequential_model.sample_weights(
            #     results_sink + "IDnet_" + video + "_sequentialNet" + ".h5"
            # )

    if network == "idtracker" or network == "both":
        dataloader.categorize_data(num_classes=num_classes)

        our_model = Model()
        # Comparison to Idtracker.ai network for animal identification
        idtracker = idtracker_ai(dataloader.get_input_shape(), num_classes)
        our_model.recognition_model = idtracker

        # Supplementary
        # optimizer default SGD, but also adam, test both
        our_model.set_optimizer("sgd", lr=0.0001)

        our_model.recognition_model_epochs = 100
        our_model.recognition_model_batch_size = 64

        CB_es = get_callbacks(patience=10, min_delta=0.05, reduce=False)
        our_model.add_callbacks([CB_es])

        my_metrics = Metrics()
        my_metrics.setModel(our_model.recognition_model)
        my_metrics.validation_data = (dataloader.x_test, dataloader.y_test)
        our_model.add_callbacks([my_metrics])

        our_model.train_recognition_network(dataloader=dataloader)
        # our_model.recognition_model.save('IdTracker_' + vidname + '_recognitionNet' + '.h5')
        res = our_model.predict(dataloader.x_test)
        results.append(
            [
                "IdTracker",
                video,
                fraction,
                metrics.balanced_accuracy_score(
                    res, np.argmax(dataloader.y_test, axis=-1)
                ),
                metrics.f1_score(
                    res, np.argmax(dataloader.y_test, axis=-1), average="macro"
                ),
            ]
        )

    if network == "shuffle":
        import random

        res = list(dataloader.y_test)
        random.shuffle(res)
        res = np.asarray(res)
        results.append(
            [
                "shuffle",
                video,
                fraction,
                metrics.balanced_accuracy_score(
                    # res, np.argmax(dataloader.y_test, axis=-1)
                    res,
                    dataloader.y_test,
                ),
                metrics.f1_score(
                    # res, np.argmax(dataloader.y_test, axis=-1), average="macro"
                    res,
                    dataloader.y_test,
                    average="macro",
                ),
            ]
        )

        print(results)

    np.save(
        results_sink + "results_df",
        results,
        allow_pickle=True,
    )


def idresults_to_training_recurrent(
    idresults, fnames_base, video, index, masking=True, mask_size=128, rescaling=False
):
    multi_imgs_x = []
    multi_imgs_y = []

    skipped = 0

    batch_size = 10000

    offset = index * batch_size

    # for 1024 is 128

    for el in idresults.keys():
        print(str(el))
        if el < 100:
            continue
        #     print(el)

        # older 1024, 1024 version
        #     fnames_base = '/media/nexus/storage1/swissknife_data/primate/inference/segmentation/20180115T150502-20180115T150902_%T1/frames/'

        #         frame = fnames_base + 'frames/' + 'frame_' + str(el) + '.npy'

        masks = idresults[el]["masks"]["masks"]
        boxes = idresults[el]["masks"]["rois"]

        for ids in range(0, min(masks.shape[-1], 4)):

            #             # TODO FIX
            #             try:
            #                 image = np.load(frame)
            #             except FileNotFoundError:
            #                 continue
            #             image = idresults[el]['frame']
            # if rescaling:
            if False:
                com = [
                    int(
                        (
                            idresults[el]["masks"]["rois"][ids][0]
                            + idresults[el]["masks"]["rois"][ids][2]
                        )
                        / 2
                    )
                    * 2,
                    int(
                        (
                            idresults[el]["masks"]["rois"][ids][1]
                            + idresults[el]["masks"]["rois"][ids][3]
                        )
                        / 2
                    )
                    * 2,
                ]
                mask = rescale(masks[:, :, ids], 0.5)
            #         mask = rescale(masks[:,:,ids], 1.0)

            else:

                # normal one
                com = [
                    int(
                        (
                            idresults[el]["masks"]["rois"][ids][0]
                            + idresults[el]["masks"]["rois"][ids][2]
                        )
                        / 2
                    ),
                    int(
                        (
                            idresults[el]["masks"]["rois"][ids][1]
                            + idresults[el]["masks"]["rois"][ids][3]
                        )
                        / 2
                    ),
                ]
                mask = masks[:, :, ids]
                mybox = boxes[ids, :]

            #         multi_imgs_y.append(int(idresults[el]['results'][ids][0])-1)

            # TODO: fixme
            if el == 2220 or el == 2395 or el == 9601:
                print(el)
                skipped += 1
                continue

            try:

                if (
                    idresults[el]["results"][ids].split("_")[0] in classes
                    and idresults[el]["results"][ids].split("_")[1] == "easy"
                ):

                    images = []

                    spacing = 3

                    dil_scaling = 5

                    if rescaling:

                        for j in range(-3, 4):
                            print("jjjjjj", j)
                            img = mold_image(video.get_data(offset + el + j * spacing))
                            print("image shape", img.shape)
                            rescaled_img = rescale_img(mybox, img)
                            images.append(rescaled_img)

                        res_images = images

                    elif masking:

                        for j in range(-3, 4):
                            images.append(
                                mask_image(
                                    mold_image(
                                        video.get_data(offset + el + j * spacing)
                                    ),
                                    mask,
                                    dilation_factor=100 * dil_scaling,
                                )
                            )

                        res_images = []

                        for image in images:

                            img = np.zeros((int(2 * mask_size), int(2 * mask_size), 3))
                            img_help = image[
                                max(com[0] - mask_size, 0) : min(
                                    com[0] + mask_size, 2048
                                ),
                                max(com[1] - mask_size, 0) : min(
                                    com[1] + mask_size, 2048
                                ),
                            ]

                            le = int(img_help.shape[0] / 2)
                            ri = img_help.shape[0] - le
                            up = int(img_help.shape[1] / 2)
                            do = img_help.shape[1] - up
                            img[
                                mask_size - le : mask_size + ri,
                                mask_size - up : mask_size + do,
                                :,
                            ] = img_help
                            img = img.astype("uint8")

                            #             break
                            if not img.shape == (
                                int(2 * mask_size),
                                int(2 * mask_size),
                                3,
                            ):
                                skipped += 1
                                print(el)
                                continue

                            res_images.append(img)

                    else:
                        for j in range(-3, 4):
                            images.append(
                                mold_image(video.get_data(offset + el + j * spacing))
                            )

                        res_images = []

                        for image in images:

                            img = np.zeros((int(2 * mask_size), int(2 * mask_size), 3))
                            img_help = image[
                                max(com[0] - mask_size, 0) : min(
                                    com[0] + mask_size, 2048
                                ),
                                max(com[1] - mask_size, 0) : min(
                                    com[1] + mask_size, 2048
                                ),
                            ]

                            le = int(img_help.shape[0] / 2)
                            ri = img_help.shape[0] - le
                            up = int(img_help.shape[1] / 2)
                            do = img_help.shape[1] - up
                            img[
                                mask_size - le : mask_size + ri,
                                mask_size - up : mask_size + do,
                                :,
                            ] = img_help
                            img = img.astype("uint8")

                            #             break
                            if not img.shape == (
                                int(2 * mask_size),
                                int(2 * mask_size),
                                3,
                            ):
                                skipped += 1
                                print(el)
                                continue

                            res_images.append(img)

                    res_images = np.asarray(res_images)
                    multi_imgs_y.append(
                        classes[idresults[el]["results"][ids].split("_")[0]]
                    )
                    multi_imgs_x.append(res_images)
            except KeyError:
                continue

    X = np.asarray(multi_imgs_x)
    y = np.asarray(multi_imgs_y)

    return X, y


def load_vid(basepath, vid, idx, batch_size=10000):
    videodata = loadVideo(basepath + vid + ".mp4", greyscale=False)
    videodata = videodata[idx * batch_size : (idx + 1) * batch_size]
    results_list = Parallel(
        n_jobs=-1, max_nbytes=None, backend="multiprocessing", verbose=40
    )(delayed(mold_image)(image) for image in videodata)
    results = {}
    for idx, el in enumerate(results_list):
        results[idx] = el

    return results


def vid_to_xy(video):
    video = video.split("/")[-1].split("IDresults_")[-1].split(".np")[0]
    vid = video.split(".npy")[0][:-2]
    vidlist.append(vid)
    idx = int(video.split(".npy")[0][-1:])
    idx -= 1

    idresults = np.load(
        idresults_base + "IDresults_" + video + ".npy", allow_pickle=True
    ).item()
    pat = vid_basepath + vid + ".mp4"
    print(pat)
    vid = imageio.get_reader(pat, "ffmpeg")
    #     vid = load_vid(vid_basepath,vid,idx)

    _X, _y = idresults_to_training_recurrent(
        idresults, fnames_base + video + "/", vid, idx, mask_size=mask_size
    )

    return [_X, _y]


def main():
    # TODO: replace
    args = parser.parse_args()
    operation = args.operation
    network = args.network
    gpu_name = args.gpu
    config_name = args.config
    video = args.video
    fraction = args.fraction
    cv_folds = args.cv_folds
    fold = args.fold
    nw_path = args.nw_path
    images = args.images
    annotations = args.annotations
    results_sink = args.results_sink
    training_data = args.training_data
    species = args.species

    config = load_config("../configs/identification/" + config_name)
    # TODO: fix and remove
    config["use_generator"] = False

    set_random_seed(config["random_seed"])
    setGPU(gpu_name=gpu_name)

    x_train = []
    y_train = []
    x_test = []
    y_test = []

    if training_data is not None:
        training_folders = training_data + "train/"
        testing_folders = training_data + "val/"

        # go through each subfolder in testing_folder
        for training_folder in os.listdir(training_folders):
            animal_id = training_folder[-1]
            # load every image file in testing_folder
            training_images = [
                imageio.imread(training_folders + training_folder + "/" + f)
                for f in os.listdir(training_folders + training_folder)
            ]
            # labels for each folder with the same id and length as the number of images
            training_labels = [animal_id] * len(training_images)
            # append to x_train and y_train
            x_train.extend(training_images)
            y_train.extend(training_labels)

        # convert to numpy arrays
        x_train = np.array(x_train)
        y_train = np.array(y_train)

        # go through each subfolder in testing_folder
        for testing_folder in os.listdir(testing_folders):
            animal_id = testing_folder[-1]
            # load every image file in testing_folder
            testing_images = [
                imageio.imread(testing_folders + testing_folder + "/" + f)
                for f in os.listdir(testing_folders + testing_folder)
            ]
            # labels for each folder with the same id and length as the number of images
            testing_labels = [animal_id] * len(testing_images)
            # append to x_test and y_test
            x_test.extend(testing_images)
            y_test.extend(testing_labels)

        # convert to numpy arrays
        x_test = np.array(x_test)
        y_test = np.array(y_test)

    results_sink = (
        results_sink
        + "/"
        + config_name
        + "/"
        + network
        + "/"
        + datetime.now().strftime("%Y-%m-%d-%H_%M")
        + "/"
    )

    ### dataprep
    # TODO: fcn
    # prepare crossval

    dataloader = Dataloader(x_train, y_train, x_test, y_test, config=config)

    # TODO: use config for all preproc steps
    # FIXME: remove?
    dataloader.change_dtype()

    # dataloader.normalize_data()

    # preproc labels
    print("encoding")
    dataloader.encode_labels()

    # dataloader.expand_dims()

    video = "mouse"

    # TODO: implement recurrent dataloader
    if config["train_sequential_model"]:
        dataloader.create_recurrent_data()

    # dataloader.undersample_data()

    train_on_data(
        species=species,
        network=network,
        config=config,
        results_sink=results_sink,
        dataloader=dataloader,
        fraction=fraction,
        cv_folds=cv_folds,
        fold=fold,
        masking=config["masking"],
    )

    if operation == "train_primate_cv":
        results_sink = (
            "/media/nexus/storage5/swissknife_results/identification/"
            + "primate/"
            + config["experiment_name"]
            + "_"
            + network
            + "_CV_"
            + "fraction_"
            + str(fraction)
            + "_"
            + datetime.now().strftime("%Y-%m-%d-%H_%M")
            + "/"
        )
        check_directory(results_sink)
        X, y, vidlist = get_primate_identification_data(scaled=True)
        videos = np.unique(vidlist)
        print(videos)
        for video in videos:
            print("VIDEO")
            print(video)
            train_on_data(
                species="primate",
                network=network,
                config=config,
                results_sink=results_sink,
                video=video,
                fraction=fraction,
            )

    if operation == "train_primate":
        results_sink = (
            "/media/nexus/storage5/swissknife_results/identification/"
            + "primate/"
            + config["experiment_name"]
            + "_"
            + network
            + "_"
            + datetime.now().strftime("%Y-%m-%d-%H_%M")
            + "/"
        )
        check_directory(results_sink)

        train_on_data(
            species="primate",
            network=network,
            config=config,
            results_sink=results_sink,
            video=video,
            fraction=fraction,
            masking=config["masking"],
        )
    if operation == "train_mouse":
        results_sink = (
            # "/media/nexus/storage5/swissknife_results/identification/"
            "/media/nexus/storage5/swissknife_results/identification_masked/"
            + "mouse/"
            + config["experiment_name"]
            + "_"
            + network
            + "_"
            + str(fraction)
            + "_fold_"
            + str(fold)
            + datetime.now().strftime("%Y-%m-%d-%H_%M")
            + "/"
        )
        # check_directory(results_sink)
        train_on_data(
            species="mouse",
            network=network,
            config=config,
            results_sink=results_sink,
            fraction=fraction,
            cv_folds=cv_folds,
            fold=fold,
            masking=config["masking"],
        )
    if operation == "evaluate_primate":
        evaluate_on_data(
            species="primate",
            # network="../results/identification/"
            # network = "/media/nexus/storage5/swissknife_results/identification/primate/identification_full_CV_2020-06-18-00_54/"
            network="/media/nexus/storage5/swissknife_results/identification/old/identification_full_ours_CV_fraction_1.0_2020-07-13-10_33/"
            + video
            + "/IDnet_"
            + video
            + "_recognitionNet.h5",
            video=video,
            exclude_hard=True,
        )

    if operation == "evaluate_mouse_multi":
        evaluate_on_data(
            species="mouse_crossday",
            network=nw_path,
            config=config,
            masking=config["masking"],
        )

    # save config
    with open(results_sink + "config.json", "w") as f:
        json.dump(config, f)
    f.close()

    print("DONE")


parser = ArgumentParser()
parser.add_argument(
    "--species",
    action="store",
    dest="species",
    type=str,
    default="mouse",
    help="which species to train/infer on",
)
parser.add_argument(
    "--config",
    action="store",
    dest="config",
    type=str,
    default="identification_config",
    help="config for specifying training params",
)
parser.add_argument(
    "--video",
    action="store",
    dest="video",
    type=str,
    default=None,
    help="which video to train/infer on",
)
parser.add_argument(
    "--network",
    action="store",
    dest="network",
    type=str,
    default="ours",
    help="which network used for training",
)
parser.add_argument(
    "--operation",
    action="store",
    dest="operation",
    type=str,
    default="",
    help="standard training options for SIPEC data",
)
parser.add_argument(
    "--gpu",
    action="store",
    dest="gpu",
    type=str,
    default="0",
    help="filename of the video to be processed (has to be a segmented one)",
)

parser.add_argument(
    "--fraction",
    action="store",
    dest="fraction",
    type=float,
    default=None,
    help="fraction to use for training",
)

parser.add_argument(
    "--fold",
    action="store",
    dest="fold",
    type=int,
    default=None,
    help="fold for crossvalidation",
)

parser.add_argument(
    "--cv_folds",
    action="store",
    dest="cv_folds",
    type=int,
    default=0,
    help="folds for cross validation",
)

parser.add_argument(
    "--nw_path",
    action="store",
    dest="nw_path",
    type=str,
    default=None,
    help="network used for evaluation",
)
parser.add_argument(
    "--videos_path",
    action="store",
    dest="videos_path",
    type=str,
    default=None,
    help="path with folder of video files of different animals",
)
parser.add_argument(
    "--npy_path",
    action="store",
    dest="npy_path",
    type=str,
    default=None,
    help="path with folder of npy files of different animals",
)

parser.add_argument(
    "--images",
    action="store",
    dest="images",
    type=str,
    default=None,
    help="path with folder images of different animals",
)

parser.add_argument(
    "--annotations",
    action="store",
    dest="annotations",
    type=str,
    default=None,
    help="path with folder annotations of different animals",
)
parser.add_argument(
    "--training_data",
    action="store",
    dest="training_data",
    type=str,
    default=None,
    help="path to folder with images of different animals split into train and test folders and individual folders for each animal",
)
parser.add_argument(
    "--results_sink",
    action="store",
    dest="results_sink",
    type=str,
    default="./results/identification/",
    help="path to results",
)

if __name__ == "__main__":
    main()
