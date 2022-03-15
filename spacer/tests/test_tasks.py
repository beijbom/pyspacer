import unittest

from PIL import Image

from spacer import config
from spacer.data_classes import ImageFeatures, ValResults, ImageLabels
from spacer.messages import \
    ExtractFeaturesMsg, \
    ExtractFeaturesReturnMsg, \
    TrainClassifierMsg, \
    TrainClassifierReturnMsg, \
    ClassifyFeaturesMsg, \
    ClassifyImageMsg, \
    ClassifyReturnMsg, \
    DataLocation
from spacer.storage import \
    store_classifier, \
    load_classifier, \
    clear_memory_storage, \
    store_image, \
    storage_factory
from spacer.tasks import \
    extract_features, \
    train_classifier, \
    classify_features, \
    classify_image
from spacer.train_utils import make_random_data
from spacer.train_utils import train

TEST_URL = \
    'https://upload.wikimedia.org/wikipedia/commons/7/7b/Red_sea_coral_reef.jpg'


class TestImageAndPointLimitsAsserts(unittest.TestCase):

    def test_image_too_large(self):
        clear_memory_storage()
        img_loc = DataLocation(storage_type='memory', key='img')

        store_image(img_loc, Image.new('RGB', (10001, 10000)))
        msg = ExtractFeaturesMsg(
            job_token='test',
            feature_extractor_name='dummy',
            image_loc=img_loc,
            rowcols=[(1, 1)],
            feature_loc=DataLocation(storage_type='memory',
                                     key='feats')
        )
        try:
            extract_features(msg)
        except AssertionError as err:
            assert "too large" in repr(err)

    def test_image_ok_size(self):
        clear_memory_storage()
        img_loc = DataLocation(storage_type='memory', key='img')

        store_image(img_loc, Image.new('RGB', (10000, 10000)))
        msg = ExtractFeaturesMsg(
            job_token='test',
            feature_extractor_name='dummy',
            image_loc=img_loc,
            rowcols=[(1, 1)],
            feature_loc=DataLocation(storage_type='memory',
                                     key='feats')
        )
        try:
            extract_features(msg)
        except AssertionError:
            self.fail("Image size assert tripped unexpectedly.")

    def test_too_many_points(self):
        clear_memory_storage()
        img_loc = DataLocation(storage_type='memory', key='img')

        store_image(img_loc, Image.new('RGB', (1000, 1000)))
        msg = ExtractFeaturesMsg(
            job_token='test',
            feature_extractor_name='dummy',
            image_loc=img_loc,
            rowcols=[(i, i) for i in range(config.MAX_POINTS_PER_IMAGE + 1)],
            feature_loc=DataLocation(storage_type='memory',
                                     key='feats')
        )
        try:
            extract_features(msg)
        except AssertionError as err:
            assert "Too many rowcol locations" in repr(err)

    def test_ok_nbr_points(self):
        clear_memory_storage()
        img_loc = DataLocation(storage_type='memory', key='img')

        store_image(img_loc, Image.new('RGB', (1000, 1000)))
        msg = ExtractFeaturesMsg(
            job_token='test',
            feature_extractor_name='dummy',
            image_loc=img_loc,
            rowcols=[(i, i) for i in range(config.MAX_POINTS_PER_IMAGE)],
            feature_loc=DataLocation(storage_type='memory',
                                     key='feats')
        )
        try:
            extract_features(msg)
        except AssertionError as err:
            self.fail("Point count assert tripped unexpectedly.")


class TestExtractFeatures(unittest.TestCase):

    def test_default(self):

        clear_memory_storage()
        img_loc = DataLocation(storage_type='memory', key='img')

        store_image(img_loc, Image.new('RGB', (100, 100)))
        msg = ExtractFeaturesMsg(
            job_token='test',
            feature_extractor_name='dummy',
            image_loc=img_loc,
            rowcols=[(1, 1), (2, 2)],
            feature_loc=DataLocation(storage_type='memory',
                                     key='feats')
        )
        return_msg = extract_features(msg)
        self.assertTrue(type(return_msg) == ExtractFeaturesReturnMsg)
        storage = storage_factory('memory')
        self.assertTrue(storage.exists('feats'))

    def test_duplicate_rowcols(self):

        msg = ExtractFeaturesMsg(
            job_token='job_nbr_1',
            feature_extractor_name='dummy',
            rowcols=[(100, 100), (50, 50), (100, 100)],
            image_loc=DataLocation(storage_type='memory',
                                   key='tmp_img'),
            feature_loc=DataLocation(storage_type='memory',
                                     key='tmp_feats')
        )
        store_image(msg.image_loc, Image.new('RGB', (110, 110)))
        _ = extract_features(msg)
        features = ImageFeatures.load(msg.feature_loc)
        self.assertEqual(len(features.point_features), len(msg.rowcols))


class TestTrainClassifier(unittest.TestCase):

    def test_default(self):

        # Set some hyper parameters for data generation
        n_traindata = 200
        n_valdata = 20
        points_per_image = 20
        feature_dim = 5
        class_list = [1, 2]

        # Create train and val data.
        features_loc_template = DataLocation(storage_type='memory', key='')

        train_labels = make_random_data(n_traindata,
                                        class_list,
                                        points_per_image,
                                        feature_dim,
                                        features_loc_template)

        val_labels = make_random_data(n_valdata,
                                      class_list,
                                      points_per_image,
                                      feature_dim,
                                      features_loc_template)

        # Train once by calling directly so that we have a previous classifier.
        for clf_type in config.CLASSIFIER_TYPES:
            clf, _ = train(train_labels, features_loc_template, 1, clf_type)

            previous_classifier_loc = DataLocation(storage_type='memory',
                                                   key='pc')
            store_classifier(previous_classifier_loc, clf)

            valresult_loc = DataLocation(storage_type='memory', key='val_res')

            msg = TrainClassifierMsg(
                job_token='test',
                trainer_name='minibatch',
                nbr_epochs=1,
                clf_type=clf_type,
                train_labels=train_labels,
                val_labels=val_labels,
                features_loc=features_loc_template,
                previous_model_locs=[previous_classifier_loc],
                model_loc=DataLocation(storage_type='memory', key='model'),
                valresult_loc=valresult_loc
            )
            return_msg = train_classifier(msg)
            self.assertTrue(type(return_msg) == TrainClassifierReturnMsg)

            # Do some checks on ValResults
            val_res = ValResults.load(valresult_loc)
            self.assertTrue(type(val_res) == ValResults)
            self.assertEqual(len(val_res.gt), len(val_res.est))
            self.assertEqual(len(val_res.gt), len(val_res.scores))

            # Check that the amount of labels correspond to the val_data.
            self.assertEqual(len(val_res.gt),
                             len(val_labels) * val_labels.samples_per_image)

    def test_duplicates(self):

        labels = ImageLabels(data={})
        for i in range(config.MIN_TRAINIMAGES):
            msg = ExtractFeaturesMsg(
                job_token='dummy',
                feature_extractor_name='dummy',
                rowcols=[(100, 100), (50, 50)],
                image_loc=DataLocation(storage_type='memory',
                                       key='{}.jpg'.format(i)),
                feature_loc=DataLocation(storage_type='memory',
                                         key='{}.json'.format(i))
            )

            # Add a duplicate that was not part of feature extraction.
            store_image(msg.image_loc, Image.new('RGB', (101, 101)))
            extract_features(msg)
            rowcols = msg.rowcols
            rowcols.append((100, 100))
            point_labels = [1, 0, 1]
            labels.data[msg.feature_loc.key] = [
                (row, col, pl) for (row, col), pl in
                zip(rowcols, point_labels)
            ]

        # Create train and val data.
        features_loc_template = DataLocation(storage_type='memory', key='')

        msg = TrainClassifierMsg(
            job_token='test',
            trainer_name='minibatch',
            nbr_epochs=1,
            clf_type='LR',
            train_labels=labels,
            val_labels=labels,
            features_loc=features_loc_template,
            previous_model_locs=[],
            model_loc=DataLocation(storage_type='memory', key='model'),
            valresult_loc=DataLocation(storage_type='memory', key='result')
        )
        return_msg = train_classifier(msg)

        # Basically make sure this doesn't raise any errors
        self.assertTrue(True)

        # Now change the rowcols in the labels file to include a tuple
        # not extracted.
        faulty_labels = ImageLabels(data={})
        for key, value in labels.data.items():
            faulty_labels.data[key] = value
            row, col, label = faulty_labels.data[key][-1]
            faulty_labels.data[key][-1] = (row-1, col-1, label)

        with self.assertRaises(AssertionError):
            train_classifier(msg)


class ClassifyReturnMsgTest(unittest.TestCase):

    def _validate_return_msg(self, return_msg, valid_rowcol):

        self.assertTrue(isinstance(return_msg.runtime, float))

        for row, col, scores in return_msg.scores:
            self.assertTrue(isinstance(scores, list))
            self.assertEqual(len(scores), len(return_msg.classes))

            if valid_rowcol:
                self.assertTrue(isinstance(return_msg[(row, col)], list))
                self.assertEqual(return_msg[(row, col)], scores)
                self.assertTrue(isinstance(row, int))
                self.assertTrue(isinstance(col, int))
            else:
                self.assertRaises(ValueError, return_msg.__getitem__, (10, 20))
                self.assertIsNone(row)
                self.assertIsNone(col)

        for class_ in return_msg.classes:
            self.assertTrue(isinstance(class_, int))

        self.assertTrue(isinstance(return_msg.valid_rowcol, bool))

        self.assertTrue(type(return_msg.scores), ClassifyReturnMsg)


class TestClassifyFeatures(ClassifyReturnMsgTest):

    def setUp(self):
        config.filter_warnings()

    @unittest.skipUnless(config.HAS_S3_TEST_ACCESS, 'No access to tests')
    def test_legacy(self):
        msg = ClassifyFeaturesMsg(
            job_token='my_job',
            feature_loc=DataLocation(storage_type='s3',
                                     bucket_name=config.TEST_BUCKET,
                                     key='legacy.jpg.feats'),
            classifier_loc=DataLocation(storage_type='s3',
                                        key='legacy.model',
                                        bucket_name=config.TEST_BUCKET)
        )

        return_msg = classify_features(msg)
        self._validate_return_msg(return_msg, False)

    @unittest.skipUnless(config.HAS_S3_TEST_ACCESS, 'No access to tests')
    def test_new(self):

        feats = ImageFeatures.make_random([1, 2, 3, 2], feature_dim=4096)
        feature_loc = DataLocation(storage_type='memory',
                                   key='new.jpg.feats')
        feats.store(feature_loc)

        model_loc = DataLocation(storage_type='s3',
                                 key='legacy.model',
                                 bucket_name=config.TEST_BUCKET)

        msg = ClassifyFeaturesMsg(
            job_token='my_job',
            feature_loc=feature_loc,
            classifier_loc=model_loc
        )

        return_msg = classify_features(msg)

        self._validate_return_msg(return_msg, True)


class TestClassifyImage(ClassifyReturnMsgTest):

    def setUp(self):
        config.filter_warnings()

    @unittest.skipUnless(config.HAS_S3_TEST_ACCESS, 'No access to tests')
    def test_deploy_simple(self):
        msg = ClassifyImageMsg(
            job_token='my_job',
            image_loc=DataLocation(storage_type='url',
                                   key=TEST_URL),
            feature_extractor_name='dummy',
            rowcols=[(100, 100), (200, 200)],
            classifier_loc=DataLocation(storage_type='s3',
                                        key='legacy.model',
                                        bucket_name=config.TEST_BUCKET)
        )
        return_msg = classify_image(msg)
        self._validate_return_msg(return_msg, True)


class TestClassifyImageCache(unittest.TestCase):

    def setUp(self):
        config.filter_warnings()

    @unittest.skipUnless(config.HAS_S3_TEST_ACCESS, 'No access to tests')
    def test_classify_image_with_caching(self):
        """ Call classify_image three times.
        The first 2 time with same message.
        The last time with a new message (different classifier).
        Due to caching, the second call should be the fastest of the three.
        """

        load_classifier.cache_clear()
        msg = ClassifyImageMsg(
            job_token='my_job',
            image_loc=DataLocation(storage_type='url',
                                   key=TEST_URL),
            feature_extractor_name='dummy',
            rowcols=[(100, 100), (200, 200)],
            classifier_loc=DataLocation(storage_type='s3',
                                        key='legacy.model',
                                        bucket_name=config.TEST_BUCKET)
        )

        msg2 = ClassifyImageMsg(
            job_token='my_job',
            image_loc=DataLocation(storage_type='url',
                                   key=TEST_URL),
            feature_extractor_name='dummy',
            rowcols=[(100, 100), (200, 200)],
            classifier_loc=DataLocation(storage_type='s3',
                                        key='legacy_model2.pkl',
                                        bucket_name=config.TEST_BUCKET)
        )

        return_msg1 = classify_image(msg)
        return_msg2 = classify_image(msg)
        return_msg3 = classify_image(msg2)
        self.assertLess(return_msg2.runtime, return_msg1.runtime)
        self.assertLess(return_msg2.runtime, return_msg3.runtime)


class TestBadRowcols(unittest.TestCase):

    def test_image_classify(self):
        msg = ClassifyImageMsg(
            job_token='my_job',
            image_loc=DataLocation(storage_type='url',
                                   key=TEST_URL),
            feature_extractor_name='dummy',
            rowcols=[(-1, -1)],
            classifier_loc=DataLocation(storage_type='s3',
                                        key='legacy.model',
                                        bucket_name=config.TEST_BUCKET)
        )

        try:
            classify_image(msg)
            raise ValueError("classify_image should raise an error.")
        except AssertionError as err:
            self.assertIn('negative', repr(err))
            self.assertIn('-1', repr(err))


if __name__ == '__main__':
    unittest.main()
