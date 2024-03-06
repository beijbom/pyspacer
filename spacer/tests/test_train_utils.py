from __future__ import annotations
import unittest

import numpy as np

from spacer import config
from spacer.data_classes import (
    Annotation, ImageLabels, PointFeatures, ImageFeatures)
from spacer.exceptions import RowColumnInvalidError, RowColumnMismatchError
from spacer.messages import DataLocation
from spacer.train_utils import (
    calc_acc,
    evaluate_classifier,
    load_batch_data,
    load_data_as_mini_batches,
    load_image_data,
    make_random_data,
    train,
)


class TestMakeRandom(unittest.TestCase):

    def test_nominal(self):

        n_traindata = 20
        points_per_image = 200
        feature_dim = 5
        class_list = [1, 2]

        features_loc_template = DataLocation(storage_type='memory', key='')

        traindata = make_random_data(n_traindata,
                                     class_list,
                                     points_per_image,
                                     feature_dim,
                                     features_loc_template)

        self.assertEqual(
            len(traindata), n_traindata,
            msg="Length (image count) should be as expected")
        self.assertEqual(
            traindata.label_count, n_traindata*points_per_image,
            msg="Label count should be as expected")

        one_feature_loc = features_loc_template
        one_feature_loc.key = traindata.image_keys[0]
        feats = ImageFeatures.load(one_feature_loc)
        self.assertEqual(
            feats.feature_dim, feature_dim,
            msg="Should have created features as expected")


class TestTrain(unittest.TestCase):

    def do_basic_run(self, class_list, clf_type):

        n_traindata = 5
        n_refdata = 1
        points_per_image = 20
        feature_dim = 5
        num_epochs = 4
        feature_loc = DataLocation(storage_type='memory', key='')

        train_labels = make_random_data(
            n_traindata, class_list, points_per_image,
            feature_dim, feature_loc,
        )
        ref_labels = make_random_data(
            n_refdata, class_list, points_per_image,
            feature_dim, feature_loc,
        )

        clf_calibrated, ref_acc = train(
            train_labels, ref_labels, feature_loc,
            num_epochs, clf_type,
        )

        self.assertEqual(
            len(ref_acc), num_epochs,
            msg="Sanity check: expecting one ref_acc element per epoch")

    def test_lr_int_labels(self):
        self.do_basic_run([1, 2], 'LR')

    def test_mlp_int_labels(self):
        self.do_basic_run([1, 2], 'MLP')

    def test_lr_str_labels(self):
        self.do_basic_run(['Porites', 'CCA', 'Sand'], 'LR')

    def test_mlp_str_labels(self):
        self.do_basic_run(['Porites', 'CCA', 'Sand'], 'MLP')

    def test_mlp_hybrid_mode(self):

        param_sets = [
            (11, 20, (100,), 1e-3),
            (100, 1000, (200, 100), 1e-4),
        ]

        for (n_traindata, points_per_image, hls, lr) in param_sets:
            feature_dim = 5
            class_list = [1, 2]
            num_epochs = 4
            feature_loc = DataLocation(storage_type='memory', key='')

            train_labels = make_random_data(
                n_traindata, class_list, points_per_image,
                feature_dim, feature_loc,
            )
            ref_labels = make_random_data(
                1, class_list, points_per_image,
                feature_dim, feature_loc,
            )

            clf_calibrated, ref_acc = train(
                train_labels, ref_labels, feature_loc, num_epochs, 'MLP')
            clf_param = clf_calibrated.get_params()['base_estimator']
            self.assertEqual(
                clf_param.hidden_layer_sizes, hls,
                msg="Hidden layer sizes should correspond to label count")
            self.assertEqual(
                clf_param.learning_rate_init, lr,
                msg="Learning rate init value should correspond to label"
                    " count")


class TestEvaluateClassifier(unittest.TestCase):

    def test_simple(self):
        class_list = [1, 2]
        points_per_image = 4
        feature_dim = 5
        feature_loc = DataLocation(storage_type='memory', key='')
        train_data = make_random_data(
            9, class_list, points_per_image, feature_dim, feature_loc)
        ref_data = make_random_data(
            1, class_list, points_per_image, feature_dim, feature_loc)
        val_data = make_random_data(
            3, class_list, points_per_image, feature_dim, feature_loc)

        for clf_type in config.CLASSIFIER_TYPES:
            clf, _ = train(train_data, ref_data, feature_loc, 1, clf_type)

            gts, ests, scores = evaluate_classifier(clf, val_data, feature_loc)
            # Sanity checks
            self.assertTrue(all([gt in class_list for gt in gts]))
            self.assertTrue(all([est in class_list for est in ests]))
            self.assertTrue(all([0 < s < 1 for s in scores]))


class TestLoadDataAsMiniBatches(unittest.TestCase):
    """
    This assumes the default batch size config value of 5000 labels.

    Ideally, later we'd be able to override config for specific tests,
    and then set an override for this test class so that it doesn't
    depend on the non-test config value.
    """

    @classmethod
    def setUpClass(cls):
        config.filter_warnings()

        cls.classes = [1, 2]
        cls.feature_dim = 5
        cls.feature_loc = DataLocation(storage_type='memory', key='')

    def test_one_non_full_batch(self):
        im_count = 20
        points_per_image = 10
        random_state = 1
        batches = [batch for batch in load_data_as_mini_batches(
            make_random_data(
                im_count, self.classes, points_per_image,
                self.feature_dim, self.feature_loc),
            self.feature_loc,
            random_state,
        )]

        self.assertEqual(len(batches), 1, msg="Should have 1 batch")
        self.assertEqual(
            len(batches[0][0]), 200, msg="Should have 200 point features")
        self.assertEqual(
            len(batches[0][1]), 200, msg="Should have 200 labels")

    def test_one_full_batch(self):
        im_count = 10
        points_per_image = 500
        random_state = 1
        batches = [batch for batch in load_data_as_mini_batches(
            make_random_data(
                im_count, self.classes, points_per_image,
                self.feature_dim, self.feature_loc),
            self.feature_loc,
            random_state,
        )]

        self.assertEqual(len(batches), 1, msg="Should have 1 batch")
        self.assertEqual(
            len(batches[0][0]), 5000, msg="Should have 5000 point features")
        self.assertEqual(
            len(batches[0][1]), 5000, msg="Should have 5000 labels")

    def test_multiple_batches(self):
        im_count = 21
        points_per_image = 500
        random_state = 1
        batches = [batch for batch in load_data_as_mini_batches(
            make_random_data(
                im_count, self.classes, points_per_image,
                self.feature_dim, self.feature_loc),
            self.feature_loc,
            random_state,
        )]

        self.assertEqual(len(batches), 3, msg="Should have 3 batches")
        self.assertEqual(
            len(batches[0][0]), 5000,
            msg="Batch 1 should have 5000 point features")
        self.assertEqual(
            len(batches[0][1]), 5000, msg="Batch 1 should have 5000 labels")
        self.assertEqual(
            len(batches[1][0]), 5000,
            msg="Batch 2 should have 5000 point features")
        self.assertEqual(
            len(batches[1][1]), 5000, msg="Batch 2 should have 5000 labels")
        self.assertEqual(
            len(batches[2][0]), 500,
            msg="Batch 3 should have 500 point features")
        self.assertEqual(
            len(batches[2][1]), 500, msg="Batch 3 should have 500 labels")

    def test_one_image_split_between_batches(self):
        im_count = 1
        points_per_image = 5001
        random_state = 1
        batches = [batch for batch in load_data_as_mini_batches(
            make_random_data(
                im_count, self.classes, points_per_image,
                self.feature_dim, self.feature_loc),
            self.feature_loc,
            random_state,
        )]

        self.assertEqual(len(batches), 2, msg="Should have 2 batches")
        self.assertEqual(
            len(batches[0][0]), 5000,
            msg="Batch 1 should have 5000 point features")
        self.assertEqual(
            len(batches[0][1]), 5000, msg="Batch 1 should have 5000 labels")
        self.assertEqual(
            len(batches[1][0]), 1, msg="Batch 2 should have 1 point feature")
        self.assertEqual(
            len(batches[1][1]), 1, msg="Batch 2 should have 1 label")

    def test_repeatable_with_same_random_state(self):
        im_count = 20
        points_per_image = 1
        random_state = 13
        data = make_random_data(
            im_count, self.classes, points_per_image,
            self.feature_dim, self.feature_loc)

        batches_1 = [batch for batch in load_data_as_mini_batches(
            data,
            self.feature_loc,
            random_state,
        )]
        batches_2 = [batch for batch in load_data_as_mini_batches(
            data,
            self.feature_loc,
            random_state,
        )]

        # Should be pretty unlikely that two random-shuffled
        # 20-feature lists get the same ordering, unless they were
        # seeded the same.
        batches_1_features = [feature for feature in batches_1[0][0]]
        batches_2_features = [feature for feature in batches_2[0][0]]
        for i in range(im_count):
            self.assertTrue(
                np.array_equal(batches_1_features[i], batches_2_features[i]),
                msg=f"Element {i} in both batch sets should be the same")


class TestAcc(unittest.TestCase):

    def test_simple(self):
        self.assertEqual(calc_acc([1, 2, 3, 11], [1, 2, 1, 4]), 0.5)
        self.assertRaises(ValueError, calc_acc, [], [])
        self.assertRaises(ValueError, calc_acc, [1], [2, 1])


class TestLoadImageData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        config.filter_warnings()
        cls.feat_key = 'tmp_features'
        cls.feature_loc = DataLocation(storage_type='memory',
                                       key=cls.feat_key)

    def fixtures(self, in_order=True, valid_rowcol=True) \
            -> tuple[list[Annotation], ImageFeatures]:

        labels = [(100, 100, 1),
                  (200, 200, 2),
                  (300, 300, 1)]

        fv1 = [1.1, 1.2, 1.3]
        fv2 = [2.1, 2.2, 2.3]
        fv3 = [3.1, 3.2, 3.3]
        if in_order:
            pfs = [
                PointFeatures(100, 100, fv1),
                PointFeatures(200, 200, fv2),
                PointFeatures(300, 300, fv3),
            ]
        else:
            # Position 1 and 2 switched compared to the labels.
            pfs = [
                PointFeatures(200, 200, fv2),
                PointFeatures(100, 100, fv1),
                PointFeatures(300, 300, fv3),
            ]

        features = ImageFeatures(
            point_features=pfs,
            valid_rowcol=valid_rowcol,
            feature_dim=3,
            npoints=3
        )
        features.store(self.feature_loc)

        return labels, features

    def test_simple(self):

        labels, features = self.fixtures(in_order=True)

        x, y = zip(*load_image_data(labels, self.feature_loc))

        self.assertEqual(list(y), [1, 2, 1])
        self.assertTrue(np.array_equal(x[0], features.point_features[0].data))

    def test_scrambled(self):
        """
        Here the feature ordering is scrambled.
        But the load result is still the same thanks to row, col matching.
        """
        labels, features = self.fixtures(in_order=False)

        x, y = zip(*load_image_data(labels, self.feature_loc))

        self.assertEqual(list(y), [1, 2, 1])
        # Same elements, different order relative to features.
        self.assertTrue(np.array_equal(x[0], features.point_features[1].data))
        self.assertTrue(np.array_equal(x[1], features.point_features[0].data))
        self.assertTrue(np.array_equal(x[2], features.point_features[2].data))

    def test_legacy(self):
        """
        Here we pretend the features are legacy such that row, col
        information is not available.
        """
        labels, features = self.fixtures(valid_rowcol=False)

        with self.assertRaises(RowColumnInvalidError) as cm:
            # Use next() to run the match_features_and_labels() generator.
            next(load_image_data(labels, self.feature_loc))
        self.assertEqual(
            str(cm.exception),
            f"{self.feat_key}: Features without rowcols are no longer"
            f" supported for training.")

    def test_rowcol_mismatch(self):
        """
        Labels has a row-column pair that's not in features.
        """
        labels, features = self.fixtures(in_order=True, valid_rowcol=True)

        labels[2] = (300, 299, 1)

        with self.assertRaises(RowColumnMismatchError) as cm:
            _, _ = load_image_data(labels, self.feature_loc)
        self.assertEqual(
            str(cm.exception),
            f"{self.feat_key}: The labels' row-column positions don't match"
            f" those of the feature vector (example: (300, 299)).")


class TestLoadBatchData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        config.filter_warnings()
        cls.feat_key1 = 'tmp_features1'
        cls.feat_key2 = 'tmp_features2'
        cls.feat1_loc = DataLocation(storage_type='memory',
                                     key='tmp_features1')
        cls.feat2_loc = DataLocation(storage_type='memory',
                                     key='tmp_features2')
        cls.feat_loc_template = DataLocation(storage_type='memory', key='')

    def fixtures(self, valid_rowcol=True) \
            -> tuple[ImageLabels, ImageFeatures, ImageFeatures]:

        labels = ImageLabels(
            data={self.feat_key1: [(100, 100, 1),
                                   (200, 200, 2),
                                   (300, 300, 1)],
                  self.feat_key2: [(10, 10, 1),
                                   (20, 20, 2),
                                   (30, 30, 1)]})

        features1 = ImageFeatures(
            point_features=[
                PointFeatures(100, 100, [1.1, 1.2, 1.3]),
                PointFeatures(200, 200, [2.1, 2.2, 2.3]),
                PointFeatures(300, 300, [3.1, 3.2, 3.3]),
            ],
            valid_rowcol=valid_rowcol,
            feature_dim=3,
            npoints=3
        )
        features1.store(self.feat1_loc)

        features2 = ImageFeatures(
            point_features=[
                PointFeatures(10, 10, [10.1, 10.2, 10.3]),
                PointFeatures(20, 20, [20.1, 20.2, 20.3]),
                PointFeatures(30, 30, [30.1, 30.2, 30.3]),
            ],
            valid_rowcol=valid_rowcol,
            feature_dim=3,
            npoints=3
        )
        features2.store(self.feat2_loc)

        return labels, features1, features2

    def test_simple(self):

        labels, features1, features2 = self.fixtures(valid_rowcol=True)
        x, y = load_batch_data(labels, self.feat_loc_template)

        for a, b in [
            (x[0], features1.point_features[0].data),
            (x[1], features1.point_features[1].data),
            (x[2], features1.point_features[2].data),
            (x[3], features2.point_features[0].data),
            (x[4], features2.point_features[1].data),
            (x[5], features2.point_features[2].data),
        ]:
            self.assertTrue(np.array_equal(a, b))


if __name__ == '__main__':
    unittest.main()
