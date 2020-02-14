import json
import os
import unittest

from spacer import config

from spacer.messages import \
    ExtractFeaturesMsg, \
    ExtractFeaturesReturnMsg, \
    TrainClassifierMsg, \
    PointFeatures, \
    ImageFeatures, \
    FeatureLabels, \
    ValResults


class TestExtractFeaturesMsg(unittest.TestCase):

    def test_serialize(self):

        msg = ExtractFeaturesMsg.example()
        self.assertEqual(msg, ExtractFeaturesMsg.deserialize(
            msg.serialize()))
        self.assertEqual(msg, ExtractFeaturesMsg.deserialize(
            json.loads(json.dumps(msg.serialize()))))

    def test_missing_fields_in_serialized_message(self):

        data = ExtractFeaturesMsg.example().serialize()
        del data['pk']  # Delete one of the keys.
        self.assertRaises(TypeError, ExtractFeaturesMsg.deserialize, data)

    def test_missing_storage_type_in_serialized_message(self):

        data = ExtractFeaturesMsg.example().serialize()
        #  Delete storage_key. Should still work since it is optional.
        del data['storage_type']
        msg = ExtractFeaturesMsg.deserialize(data)
        self.assertEqual(msg.storage_type, 's3')

    def test_asserts(self):
        msg = ExtractFeaturesMsg.example()
        msg.storage_type = 'invalid_storage'
        self.assertRaises(AssertionError,
                          ExtractFeaturesMsg.deserialize,
                          msg.serialize())

        msg = ExtractFeaturesMsg.example()
        msg.modelname = 'invalid_modelname'
        self.assertRaises(AssertionError,
                          ExtractFeaturesMsg.deserialize,
                          msg.serialize())

        msg = ExtractFeaturesMsg.example()
        msg.rowcols = []
        self.assertRaises(AssertionError,
                          ExtractFeaturesMsg.deserialize,
                          msg.serialize())

        msg = ExtractFeaturesMsg.example()
        msg.rowcols = [(120, 101, 121)]
        self.assertRaises(AssertionError,
                          ExtractFeaturesMsg.deserialize,
                          msg.serialize())


class TestExtractFeaturesReturnMsg(unittest.TestCase):

    def test_serialize(self):

        msg = ExtractFeaturesReturnMsg.example()
        self.assertEqual(msg, ExtractFeaturesReturnMsg.deserialize(
            msg.serialize()))
        self.assertEqual(msg, ExtractFeaturesReturnMsg.deserialize(
            json.loads(json.dumps(msg.serialize()))))


class TestTrainClassifierMsg(unittest.TestCase):

    def test_serialize(self):

        msg = TrainClassifierMsg.example()
        self.assertEqual(msg, TrainClassifierMsg.deserialize(
            msg.serialize()))
        self.assertEqual(msg, TrainClassifierMsg.deserialize(
            json.loads(json.dumps(msg.serialize()))))


class TestPointFeatures(unittest.TestCase):

    def test_serialize(self):

        msg = PointFeatures.example()
        self.assertEqual(msg, PointFeatures.deserialize(
            msg.serialize()))
        self.assertEqual(msg, PointFeatures.deserialize(
            json.loads(json.dumps(msg.serialize()))))


class TestImageFeatures(unittest.TestCase):

    def test_serialize(self):

        msg = ImageFeatures.example()
        self.assertEqual(msg, ImageFeatures.deserialize(
            msg.serialize()))
        self.assertEqual(msg, ImageFeatures.deserialize(
            json.loads(json.dumps(msg.serialize()))))

    def test_legacy(self):
        """
        Loads a legacy feature file and make sure it's parsed correctly.
        """
        with open(os.path.join(config.LOCAL_FIXTURE_DIR,
                               'legacy.jpg.feats')) as fp:
            msg = ImageFeatures.deserialize(json.load(fp))
        self.assertEqual(msg.valid_rowcol, False)
        self.assertEqual(ImageFeatures.deserialize(
            msg.serialize()).valid_rowcol, False)

        self.assertTrue(isinstance(msg.point_features[0], PointFeatures))
        self.assertEqual(msg.npoints, len(msg.point_features))
        self.assertEqual(msg.feature_dim, len(msg.point_features[0].data))

        self.assertEqual(msg, ImageFeatures.deserialize(msg.serialize()))
        self.assertEqual(msg, ImageFeatures.deserialize(json.loads(
            json.dumps(msg.serialize()))))

    def test_getitem(self):
        msg = ImageFeatures.example()
        point_features = msg[(100, 100)]
        self.assertEqual(point_features.data[0], 1.1)


class TestFeatureLabels(unittest.TestCase):

    def test_serialize(self):

        msg = FeatureLabels.example()
        self.assertEqual(msg, FeatureLabels.deserialize(
            msg.serialize()))
        self.assertEqual(msg, FeatureLabels.deserialize(
            json.loads(json.dumps(msg.serialize()))))

    def test_samples_per_image(self):
        msg = FeatureLabels.example()
        self.assertEqual(msg.samples_per_image, 2)


class TestValResults(unittest.TestCase):

    def test_serialize(self):

        msg = ValResults.example()
        self.assertEqual(msg, ValResults.deserialize(
            msg.serialize()))
        self.assertEqual(msg, ValResults.deserialize(
            json.loads(json.dumps(msg.serialize()))))