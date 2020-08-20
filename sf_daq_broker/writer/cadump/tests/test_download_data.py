import unittest
from unittest import TestCase
from cadump import cadump
import logging

class TestDownloadData(TestCase):

    def test_download_data(self):
        config = {
            'range': {
                'startPulseId': 9618913001,
                'endPulseId': 9618923000
            },

            'parameters': {
                'general/created': 'test',
                'general/user': 'tester',
                'general/process': 'test_process',
                'general/instrument': 'mac',
                'output_file': 'test.h5'}    # this is usually the full path
        }

        cadump.base_url = "https://data-api.psi.ch/sf"
        cadump.download_data(config)
        # self.fail()

    def test_read_channels(self):
        channels = cadump.read_channels("channels.txt")
        logging.info(channels)
        self.assertEqual(len(channels), 4)


if __name__ == '__main__':
    unittest.main()
