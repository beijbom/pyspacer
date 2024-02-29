import random
import unittest

from PIL import Image

from spacer.data_classes import LabelId
from spacer.exceptions import RowColumnInvalidError, TrainingLabelsError
from spacer.messages import DataLocation, ImageLabels, TrainingTaskLabels
from spacer.task_utils import (
    check_extract_inputs, preprocess_labels, SplitMode)
from spacer.train_utils import make_random_data


class TestRowColChecks(unittest.TestCase):

    def test_ints(self):
        img = Image.new('RGB', (100, 100))
        rowcols = [(1.1, 1.2)]
        with self.assertRaises(RowColumnInvalidError):
            check_extract_inputs(img, rowcols, 'img')

    def test_ok(self):
        img = Image.new('RGB', (100, 100))
        rowcols = [(0, 0), (99, 99)]
        try:
            check_extract_inputs(img, rowcols, 'img')
        except AssertionError:
            self.fail("check_extract_inputs raised error unexpectedly")

    def test_negative(self):
        img = Image.new('RGB', (100, 100))
        rowcols = [(-1, -1)]
        with self.assertRaises(RowColumnInvalidError):
            check_extract_inputs(img, rowcols, 'img')

    def test_too_large(self):
        img = Image.new('RGB', (100, 100))
        rowcols = [(100, 100)]
        with self.assertRaises(RowColumnInvalidError):
            check_extract_inputs(img, rowcols, 'img')

    def test_row_too_large(self):
        img = Image.new('RGB', (100, 100))
        rowcols = [(100, 99)]

        with self.assertRaises(RowColumnInvalidError) as context:
            check_extract_inputs(img, rowcols, 'img')
        self.assertEqual(
            str(context.exception),
            "img: Row value 100 falls outside this image's"
            " valid range of 0-99.")

    def test_col_too_large(self):
        img = Image.new('RGB', (100, 100))
        rowcols = [(99, 100)]

        with self.assertRaises(RowColumnInvalidError) as context:
            check_extract_inputs(img, rowcols, 'img')
        self.assertEqual(
            str(context.exception),
            "img: Column value 100 falls outside this image's"
            " valid range of 0-99.")


class TestSplitLabels(unittest.TestCase):

    def test_train_ref_val_split(self):
        """
        Let pyspacer handle the train/ref/val split.
        """
        n_data = 20
        points_per_image = 10
        feature_dim = 5
        class_list = [1, 2]
        features_loc_template = DataLocation(storage_type='memory', key='')

        labels = preprocess_labels(make_random_data(
            n_data, class_list, points_per_image,
            feature_dim, features_loc_template,
        ))

        # 80% 10% 10%
        self.assertEqual(labels['train'].label_count, 160)
        self.assertEqual(labels['ref'].label_count, 20)
        self.assertEqual(labels['val'].label_count, 20)

    def test_train_ref_val_split_large(self):
        """
        This assumes the default batch size config value of 5000 labels.

        Ideally, later we'd be able to override config for specific tests,
        and then set an override for this test class so that it doesn't
        depend on the non-test config value.
        """
        n_data = 60
        points_per_image = 1000
        feature_dim = 5
        class_list = [1, 2]
        features_loc_template = DataLocation(storage_type='memory', key='')

        labels = preprocess_labels(make_random_data(
            n_data, class_list, points_per_image,
            feature_dim, features_loc_template,
        ))

        # 80%+ (capped to 5000 points) 10%
        self.assertEqual(labels['train'].label_count, 49000)
        self.assertEqual(labels['ref'].label_count, 5000)
        self.assertEqual(labels['val'].label_count, 6000)

    def test_custom_split_ratio(self):
        n_data = 10
        points_per_image = 10
        feature_dim = 5
        class_list = [1, 2]
        features_loc_template = DataLocation(storage_type='memory', key='')

        labels = preprocess_labels(
            make_random_data(
                n_data, class_list, points_per_image,
                feature_dim, features_loc_template,
            ),
            split_ratios=(0.2, 0.3),
        )

        # 50% 20% 30%
        self.assertEqual(labels['train'].label_count, 50)
        self.assertEqual(labels['ref'].label_count, 20)
        self.assertEqual(labels['val'].label_count, 30)

    def test_vectors_imprecise_split(self):
        n_data = 10
        points_per_image = 10
        feature_dim = 5
        class_list = [1, 2]
        features_loc_template = DataLocation(storage_type='memory', key='')

        labels = preprocess_labels(
            make_random_data(
                n_data, class_list, points_per_image,
                feature_dim, features_loc_template,
            ),
            split_ratios=(0.26, 0.24),
            split_mode=SplitMode.VECTORS,
        )

        # The rest, 26% rounded up to nearest vector, 24% rounded up to
        # nearest vector
        self.assertEqual(labels['train'].label_count, 40)
        self.assertEqual(labels['ref'].label_count, 30)
        self.assertEqual(labels['val'].label_count, 30)

    def test_points_precise_split(self):
        n_data = 10
        points_per_image = 10
        feature_dim = 5
        class_list = [1, 2]
        features_loc_template = DataLocation(storage_type='memory', key='')

        labels = preprocess_labels(
            make_random_data(
                n_data, class_list, points_per_image,
                feature_dim, features_loc_template,
            ),
            split_ratios=(0.26, 0.24),
            split_mode=SplitMode.POINTS,
        )

        # 50%, 26%, 24%; exact despite having 10 points per feature vector
        self.assertEqual(labels['train'].label_count, 50)
        self.assertEqual(labels['ref'].label_count, 26)
        self.assertEqual(labels['val'].label_count, 24)

    def test_vectors_keep_vectors_together(self):
        n_data = 10
        points_per_image = 10
        feature_dim = 5
        class_list = [1, 2]
        features_loc_template = DataLocation(storage_type='memory', key='')

        labels = preprocess_labels(
            make_random_data(
                n_data, class_list, points_per_image,
                feature_dim, features_loc_template,
            ),
            split_ratios=(0.2, 0.2),
            split_mode=SplitMode.VECTORS,
        )

        # If each vector is entirely in one set, then these should be the
        # number of vectors in each set.
        self.assertEqual(len(labels['train'].image_keys), 6)
        self.assertEqual(len(labels['ref'].image_keys), 2)
        self.assertEqual(len(labels['val'].image_keys), 2)

    def test_points_dont_keep_vectors_together(self):
        n_data = 10
        points_per_image = 10
        feature_dim = 5
        class_list = [1, 2]
        features_loc_template = DataLocation(storage_type='memory', key='')

        labels = preprocess_labels(
            make_random_data(
                n_data, class_list, points_per_image,
                feature_dim, features_loc_template,
            ),
            split_ratios=(0.2, 0.2),
            split_mode=SplitMode.POINTS,
        )

        # It should be exceedingly unlikely for every vector to have all
        # 10 of its points in one set. That is, we expect at least one
        # image key to appear in two or more sets.
        self.assertGreater(
            len(labels['train'].image_keys)
            + len(labels['ref'].image_keys)
            + len(labels['val'].image_keys),
            10,
        )

    def test_points_just_enough_annotations(self):
        n_data = 1
        points_per_image = 100
        feature_dim = 5
        class_list = [1, 2]
        features_loc_template = DataLocation(storage_type='memory', key='')

        labels = preprocess_labels(
            make_random_data(
                n_data, class_list, points_per_image,
                feature_dim, features_loc_template,
            ),
            # There is another error concerning not having 2+ unique
            # classes in the ref set which we don't want to test here, so
            # we make the ref set large enough to generally avoid that.
            # (25 random points drawn from [1, 2] probably aren't going
            # to be all 1, or all 2.)
            split_ratios=(0.25, 0.0051),
            split_mode=SplitMode.POINTS,
        )
        self.assertEqual(labels['train'].label_count, 74)
        self.assertEqual(labels['ref'].label_count, 25)
        self.assertEqual(labels['val'].label_count, 1)

    def test_points_too_few_annotations(self):
        n_data = 1
        points_per_image = 100
        feature_dim = 5
        class_list = [1, 2]
        features_loc_template = DataLocation(storage_type='memory', key='')

        with self.assertRaises(TrainingLabelsError) as cm:
            preprocess_labels(
                make_random_data(
                    n_data, class_list, points_per_image,
                    feature_dim, features_loc_template,
                ),
                split_ratios=(0.25, 0.0049),
                split_mode=SplitMode.POINTS,
            )
        self.assertEqual(
            str(cm.exception),
            f"Not enough annotations to populate train/ref/val sets."
            f" Split was calculated as 75/25/0."
            f" Each set must be non-empty.")

    def test_points_stratified_just_enough_annotations(self):
        labels = preprocess_labels(
            # classes [1, 2, 3], 25 annotations
            ImageLabels({
                '1': [*[(n, n, 1) for n in range(0, 9)],
                      *[(n, n, 2) for n in range(100, 108)],
                      *[(n, n, 3) for n in range(200, 208)]],
            }),
            split_ratios=(0.101, 0.2),
            split_mode=SplitMode.POINTS_STRATIFIED,
        )
        self.assertEqual(labels['train'].label_count, 17)
        self.assertEqual(labels['ref'].label_count, 3)
        self.assertEqual(labels['val'].label_count, 5)

    def test_points_stratified_too_few_annotations(self):
        with self.assertRaises(TrainingLabelsError) as cm:
            preprocess_labels(
                # classes [1, 2, 3], 25 annotations
                ImageLabels({
                    '1': [*[(n, n, 1) for n in range(0, 9)],
                          *[(n, n, 2) for n in range(100, 108)],
                          *[(n, n, 3) for n in range(200, 208)]],
                }),
                split_ratios=(0.099, 0.2),
                split_mode=SplitMode.POINTS_STRATIFIED,
            )
        self.assertEqual(
            str(cm.exception),
            f"Not enough annotations to populate train/ref/val sets."
            f" Split was calculated as 18/2/5."
            f" Each set's size must not be less than the number of classes"
            f" (3) to work with train_test_split().")

    @staticmethod
    def count_of_label(annotations: ImageLabels, label: LabelId):
        return len([
            anno_label for row, column, anno_label in annotations
            if anno_label == label
        ])

    def test_stratify_by_classes(self):
        labels = preprocess_labels(
            ImageLabels({
                # Annotations per class: 60, 20, 10.
                # The 60 are split between 2 groups of 50/10 so things aren't
                # completely in order.
                '1': [*[(n, n, 1) for n in range(0, 50)],
                      *[(n, n, 2) for n in range(100, 120)],
                      *[(n, n, 3) for n in range(200, 210)],
                      *[(n, n, 1) for n in range(400, 410)]],
            }),
            split_mode=SplitMode.POINTS_STRATIFIED,
        )

        self.assertEqual(
            self.count_of_label(labels.train['1'], 1), 48)
        self.assertEqual(
            self.count_of_label(labels.ref['1'], 1), 6)
        self.assertEqual(
            self.count_of_label(labels.val['1'], 1), 6)

        self.assertEqual(
            self.count_of_label(labels.train['1'], 2), 16)
        self.assertEqual(
            self.count_of_label(labels.ref['1'], 2), 2)
        self.assertEqual(
            self.count_of_label(labels.val['1'], 2), 2)

        self.assertEqual(
            self.count_of_label(labels.train['1'], 3), 8)
        self.assertEqual(
            self.count_of_label(labels.ref['1'], 3), 1)
        self.assertEqual(
            self.count_of_label(labels.val['1'], 3), 1)

    def test_stratify_with_many_uncommon_classes(self):
        # 10 of each of 100 classes.
        labels_data = []
        for class_number in range(1, 100+1):
            labels_data.extend([
                (coord, coord, class_number)
                for coord in range(class_number*10, class_number*10+10)
            ])
        # Pre-shuffle to ensure stratification doesn't rely on the ordering
        # in some way.
        random.shuffle(labels_data)
        labels = preprocess_labels(
            ImageLabels({
                '1': labels_data,
            }),
            split_mode=SplitMode.POINTS_STRATIFIED,
        )

        for class_number in range(1, 100+1):
            self.assertEqual(
                self.count_of_label(labels.train['1'], class_number), 8,
                msg=f"Class {class_number} should have 8 instances in train",
            )
            self.assertEqual(
                self.count_of_label(labels.ref['1'], class_number), 1,
                msg=f"Class {class_number} should have 1 instance in ref",
            )
            self.assertEqual(
                self.count_of_label(labels.val['1'], class_number), 1,
                msg=f"Class {class_number} should have 1 instance in val",
            )

    def test_stratify_with_too_rare_classes(self):
        """
        Classes with less than 3 annotations shouldn't cause issues
        for stratified splitting.
        We expect them to get excluded before splitting.
        """
        labels = preprocess_labels(
            ImageLabels({
                '1': [*[(n, n, 1) for n in range(0, 50)],
                      *[(n, n, 2) for n in range(100, 103)],
                      *[(n, n, 3) for n in range(200, 202)],
                      *[(n, n, 4) for n in range(300, 301)],
                      *[(n, n, 5) for n in range(400, 410)]],
            }),
            # Ensure the filtering by train+ref doesn't exclude anything,
            # by giving ref a high ratio of 40%.
            split_ratios=(0.4, 0.1),
            split_mode=SplitMode.POINTS_STRATIFIED,
        )

        included_classes = labels.train.classes_set.union(
            labels.ref.classes_set, labels.val.classes_set
        )
        self.assertSetEqual(
            {1, 2, 5}, included_classes,
            msg="Classes 3 and 4 should be excluded")

    def test_do_not_stratify(self):
        # 10 of each of 100 classes.
        labels_data = []
        for class_number in range(1, 100+1):
            labels_data.extend([
                (coord, coord, class_number)
                for coord in range(class_number*10, class_number*10+10)
            ])
        # Pre-shuffle to ensure the split doesn't rely on the ordering
        # in some way.
        random.shuffle(labels_data)
        labels = preprocess_labels(
            ImageLabels({
                '1': labels_data,
            }),
            split_mode=SplitMode.POINTS,
        )

        booleans = [
            self.count_of_label(labels.train['1'], class_number) == 8
            for class_number in range(1, 100+1)
        ]
        self.assertFalse(
            all(booleans),
            msg="The chances of perfect stratification without having"
                " stratification on should be basically zero")


class TestPreprocessLabels(unittest.TestCase):
    """
    Testing the rest of preprocess_labels() besides splitting.
    """
    def test_train_ref_1_common_class(self):
        points_per_image = 20
        feature_dim = 5
        features_loc_template = DataLocation(storage_type='memory', key='')

        with self.assertRaises(TrainingLabelsError) as cm:
            preprocess_labels(TrainingTaskLabels(
                train=make_random_data(
                    1, [1, 2], points_per_image,
                    feature_dim, features_loc_template,
                ),
                ref=make_random_data(
                    1, [2, 3], points_per_image,
                    feature_dim, features_loc_template,
                ),
                val=make_random_data(
                    1, [1, 2, 3], points_per_image,
                    feature_dim, features_loc_template,
                ),
            ))
        self.assertEqual(
            str(cm.exception),
            "Need multiple classes to do training. After preprocessing"
            " training data, there are 1 class(es) left.")

    def test_trainref_val_0_common_classes(self):
        points_per_image = 20
        feature_dim = 5
        features_loc_template = DataLocation(storage_type='memory', key='')

        with self.assertRaises(TrainingLabelsError) as cm:
            preprocess_labels(TrainingTaskLabels(
                # train+ref: 1, 2
                train=make_random_data(
                    1, [1, 2, 3], points_per_image,
                    feature_dim, features_loc_template,
                ),
                ref=make_random_data(
                    1, [1, 2], points_per_image,
                    feature_dim, features_loc_template,
                ),
                # val: 3
                val=make_random_data(
                    1, [3], points_per_image,
                    feature_dim, features_loc_template,
                ),
            ))
        self.assertEqual(
            str(cm.exception),
            "After preprocessing training data, 'val' set is empty.")

    def test_filter_by_accepted_classes(self):

        labels = preprocess_labels(
            TrainingTaskLabels(
                train=ImageLabels({
                    '1': [(100, 100, 1),
                          (200, 200, 2),
                          (300, 300, 3)],
                }),
                ref=ImageLabels({
                    '2': [(200, 200, 2),
                          (300, 300, 3),
                          (100, 100, 1)],
                }),
                val=ImageLabels({
                    '3': [(300, 300, 3),
                          (100, 100, 1),
                          (200, 200, 2)],
                    '4': [(100, 300, 3),
                          (200, 100, 4),
                          (300, 200, 3)],
                }),
            ),
            # Filter to just 1 and 2. Note that, if not for passing this kwarg,
            # it'd auto filter to 1, 2, 3 because those are all in train+ref.
            accepted_classes={1, 2},
        )

        self.assertEqual(labels.train['1'], [(100, 100, 1), (200, 200, 2)])
        self.assertEqual(labels.ref['2'], [(200, 200, 2), (100, 100, 1)])
        self.assertEqual(labels.val['3'], [(100, 100, 1), (200, 200, 2)])
        self.assertNotIn(
            '4', labels.val, msg="Image 4 should be excluded entirely")


if __name__ == '__main__':
    unittest.main()
