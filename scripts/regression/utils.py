from __future__ import annotations
import glob
import json
import os
import random

import tqdm

from spacer import config
from spacer.data_classes import ImageLabels
from spacer.messages import DataLocation, ExtractFeaturesMsg
from spacer.tasks import extract_features
from spacer.train_classifier import trainer_factory


def cache_local(source_root: str,
                image_root: str,
                export_name: str,
                source_id: int,
                cache_image: bool,
                cache_feats: bool) -> None:
    # Download data to the local to speed up training
    s3 = config.get_s3_resource()
    bucket = s3.Bucket('spacer-trainingdata')
    if not os.path.exists(source_root):
        os.system('mkdir -p ' + source_root)
    if not os.path.exists(image_root):
        os.system('mkdir -p ' + image_root)

    obj = bucket.Object('{}/s{}/meta.json'.format(export_name, source_id))
    obj.download_file(os.path.join(source_root, 'meta.json'))
    all_objs = bucket.objects.filter(Prefix='{}/s{}/images'.format(export_name,
                                                                   source_id))
    selected_objs = [obj for obj in all_objs if obj.key.endswith(
        ('anns.json', 'meta.json'))]
    if cache_image:
        selected_objs += [obj for obj in all_objs if
                          obj.key.endswith(('jpg', 'png'))]
    if cache_feats:
        selected_objs += [obj for obj in all_objs if
                          obj.key.endswith('features.json')]

    print("Downloading {} metadata and image/feature files...".
          format(len(selected_objs)))
    random.shuffle(selected_objs)
    for obj in tqdm.tqdm(selected_objs):
        _, filename = obj.key.split('images')
        local_path = os.path.join(image_root, filename.lstrip('/'))
        if not os.path.exists(local_path):
            bucket.Object(obj.key).download_file(local_path)


def build_traindata(image_root: str) -> tuple[ImageLabels, ImageLabels]:

    print('Assembling data in {}...'.format(image_root))
    # Create the train and val ImageLabels data structures.
    ann_files = glob.glob(os.path.join(image_root, "*.anns.json"))
    train_labels = ImageLabels(data={})
    val_labels = ImageLabels(data={})
    for itt, ann_file in enumerate(ann_files):

        meta_file = ann_file.replace('anns', 'meta')
        features_file = ann_file.replace('anns', 'features')

        with open(ann_file) as fp:
            anns = json.load(fp)

        with open(meta_file) as fp:
            meta = json.load(fp)

        if meta['in_trainset']:
            labels = train_labels
        else:
            assert meta['in_valset']
            labels = val_labels

        labels.data[features_file] = [
            (ann['row']-1, ann['col']-1, ann['label']) for ann in anns
        ]
    return train_labels, val_labels


def do_training(source_root: str,
                train_labels: ImageLabels,
                val_labels: ImageLabels,
                n_epochs: int,
                clf_type: str) -> None:
    print("Training classifier for source {}...".format(source_root))

    feature_loc = DataLocation(storage_type='filesystem', key='')

    trainer = trainer_factory('minibatch')
    clf, val_results, return_message = trainer(
        train_labels, val_labels, n_epochs, [], feature_loc, clf_type)
    with open(os.path.join(source_root, 'meta.json')) as fp:
        source_meta = json.load(fp)

    print('Re-trained {} ({}). Old acc: {:.1f}, new acc: {:.1f}'.format(
        source_meta['name'],
        source_meta['pk'],
        100 * float(source_meta['best_robot_accuracy']),
        100 * return_message.acc)
    )


def do_extract_features(extractor_name, image_root):

    img_keys = [os.path.join(image_root, key) for key in
                os.listdir(image_root) if key.endswith('jpg')]

    print("Extracting features for images in {}".format(image_root))
    for im_key in tqdm.tqdm(img_keys):
        feature_path = im_key.replace('jpg', 'features.json')
        anns_path = im_key.replace('jpg', 'anns.json')
        if not os.path.exists(feature_path):
            with open(anns_path, 'r') as f:
                anns = json.load(f)

            msg = ExtractFeaturesMsg(
                job_token=im_key,
                feature_extractor_name=extractor_name,
                rowcols=[(ann['row']-1, ann['col']-1) for ann in anns],
                image_loc=DataLocation(
                    storage_type='filesystem',
                    key=im_key),
                feature_loc=DataLocation(
                    storage_type='filesystem',
                    key=feature_path
                )
            )
            _ = extract_features(msg)
