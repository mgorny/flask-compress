import unittest
import os

from flask import Flask, render_template

from flask_compress import Compress


class DefaultsTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.testing = True

        Compress(self.app)

    def test_mimetypes_default(self):
        """ Tests COMPRESS_MIMETYPES default value is correctly set. """
        defaults = ['text/html', 'text/css', 'text/xml', 'application/json',
                    'application/javascript']
        self.assertEqual(self.app.config['COMPRESS_MIMETYPES'], defaults)

    def test_level_default(self):
        """ Tests COMPRESS_LEVEL default value is correctly set. """
        self.assertEqual(self.app.config['COMPRESS_LEVEL'], 6)

    def test_min_size_default(self):
        """ Tests COMPRESS_MIN_SIZE default value is correctly set. """
        self.assertEqual(self.app.config['COMPRESS_MIN_SIZE'], 500)

    def test_algorithm_default(self):
        """ Tests COMPRESS_ALGORITHM default value is correctly set. """
        self.assertEqual(self.app.config['COMPRESS_ALGORITHM'], 'gzip')


class InitTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.testing = True

    def test_constructor_init(self):
        Compress(self.app)

    def test_delayed_init(self):
        compress = Compress()
        compress.init_app(self.app)


class UrlTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.testing = True

        small_path = os.path.join(os.getcwd(), 'tests', 'templates',
                                  'small.html')

        large_path = os.path.join(os.getcwd(), 'tests', 'templates',
                                  'large.html')

        self.small_size = os.path.getsize(small_path) - 1
        self.large_size = os.path.getsize(large_path) - 1

        Compress(self.app)

        @self.app.route('/small/')
        def small():
            return render_template('small.html')

        @self.app.route('/large/')
        def large():
            return render_template('large.html')

    def client_get(self, ufs):
        client = self.app.test_client()
        response = client.get(ufs, headers=[('Accept-Encoding', 'gzip')])
        self.assertEqual(response.status_code, 200)
        return response

    def test_br_algorithm(self):
        client = self.app.test_client()
        headers = [('Accept-Encoding', 'br')]

        response = client.options('/small/', headers=headers)
        self.assertEqual(response.status_code, 200)

        response = client.options('/large/', headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_compress_level(self):
        """ Tests COMPRESS_LEVEL correctly affects response data. """
        self.app.config['COMPRESS_LEVEL'] = 1
        response = self.client_get('/large/')
        response1_size = len(response.data)

        self.app.config['COMPRESS_LEVEL'] = 6
        response = self.client_get('/large/')
        response6_size = len(response.data)

        self.assertNotEqual(response1_size, response6_size)

    def test_compress_min_size(self):
        """ Tests COMPRESS_MIN_SIZE correctly affects response data. """
        response = self.client_get('/small/')
        self.assertEqual(self.small_size, len(response.data))

        response = self.client_get('/large/')
        self.assertNotEqual(self.large_size, len(response.data))

    def test_mimetype_mismatch(self):
        """ Tests if mimetype not in COMPRESS_MIMETYPES. """
        response = self.client_get('/static/1.png')
        self.assertEqual(response.mimetype, 'image/png')

    def test_content_length_options(self):
        client = self.app.test_client()
        headers = [('Accept-Encoding', 'gzip')]
        response = client.options('/small/', headers=headers)
        self.assertEqual(response.status_code, 200)


class CompressionAlgoTests(unittest.TestCase):
    """
    Test different scenarios for compression algorithm negotiation between
    client and server. Please note that algorithm names (even the "supported"
    ones) in these tests **do not** indicate that all of these are actually
    supported by this extension.
    """
    def setUp(self):
        super(CompressionAlgoTests, self).setUp()

        self.app = Flask(__name__)
        self.app.testing = True

    def test_setting_compress_algorithm_simple_string(self):
        """ Test that a single entry in `COMPRESS_ALGORITHM` still works for backwards compatibility """
        self.app.config['COMPRESS_ALGORITHM'] = 'gzip'
        c = Compress(self.app)
        self.assertListEqual(c.enabled_algorithms, ['gzip'])

    def test_setting_compress_algorithm_cs_string(self):
        """ Test that `COMPRESS_ALGORITHM` can be a comma-separated string """
        self.app.config['COMPRESS_ALGORITHM'] = 'gzip, br, zstd'
        c = Compress(self.app)
        self.assertListEqual(c.enabled_algorithms, ['gzip', 'br', 'zstd'])

    def test_setting_compress_algorithm_list(self):
        """ Test that `COMPRESS_ALGORITHM` can be a list of strings """
        self.app.config['COMPRESS_ALGORITHM'] = ['gzip', 'br', 'deflate']
        c = Compress(self.app)
        self.assertListEqual(c.enabled_algorithms, ['gzip', 'br', 'deflate'])

    def test_one_algo_supported(self):
        """ Tests requesting a single supported compression algorithm """
        accept_encoding = 'gzip'
        self.app.config['COMPRESS_ALGORITHM'] = ['br', 'gzip']
        c = Compress(self.app)
        self.assertEqual(c._choose_compress_algorithm(accept_encoding), 'gzip')

    def test_one_algo_unsupported(self):
        """ Tests requesting single unsupported compression algorithm """
        accept_encoding = 'some-alien-algorithm'
        self.app.config['COMPRESS_ALGORITHM'] = ['br', 'gzip']
        c = Compress(self.app)
        self.assertIsNone(c._choose_compress_algorithm(accept_encoding))

    def test_multiple_algos_supported(self):
        """ Tests requesting multiple supported compression algorithms """
        accept_encoding = 'br, gzip, zstd'
        self.app.config['COMPRESS_ALGORITHM'] = ['zstd', 'br', 'gzip']
        c = Compress(self.app)
        # When the decision is tied, we expect to see the first server-configured algorithm
        self.assertEqual(c._choose_compress_algorithm(accept_encoding), 'zstd')

    def test_multiple_algos_unsupported(self):
        """ Tests requesting multiple unsupported compression algorithms """
        accept_encoding = 'future-algo, alien-algo, forbidden-algo'
        self.app.config['COMPRESS_ALGORITHM'] = ['zstd', 'br', 'gzip']
        c = Compress(self.app)
        self.assertIsNone(c._choose_compress_algorithm(accept_encoding))

    def test_multiple_algos_with_wildcard(self):
        """ Tests requesting multiple unsupported compression algorithms and a wildcard """
        accept_encoding = 'future-algo, alien-algo, forbidden-algo, *'
        self.app.config['COMPRESS_ALGORITHM'] = ['zstd', 'br', 'gzip']
        c = Compress(self.app)
        # We expect to see the first server-configured algorithm
        self.assertEqual(c._choose_compress_algorithm(accept_encoding), 'zstd')

    def test_multiple_algos_with_different_quality(self):
        """ Tests requesting multiple supported compression algorithms with different q-factors """
        accept_encoding = 'zstd;q=0.8, br;q=0.9, gzip;q=0.5'
        self.app.config['COMPRESS_ALGORITHM'] = ['zstd', 'br', 'gzip']
        c = Compress(self.app)
        self.assertEqual(c._choose_compress_algorithm(accept_encoding), 'br')

    def test_multiple_algos_with_equal_quality(self):
        """ Tests requesting multiple supported compression algorithms with equal q-factors """
        accept_encoding = 'zstd;q=0.5, br;q=0.5, gzip;q=0.5'
        self.app.config['COMPRESS_ALGORITHM'] = ['gzip', 'br', 'zstd']
        c = Compress(self.app)
        # We expect to see the first server-configured algorithm
        self.assertEqual(c._choose_compress_algorithm(accept_encoding), 'gzip')

    def test_default_quality_is_1(self):
        """ Tests that when making mixed-quality requests, the default q-factor is 1.0 """
        accept_encoding = 'deflate, br;q=0.999, gzip;q=0.5'
        self.app.config['COMPRESS_ALGORITHM'] = ['gzip', 'br', 'deflate']
        c = Compress(self.app)
        self.assertEqual(c._choose_compress_algorithm(accept_encoding), 'deflate')

    def test_default_wildcard_quality_is_0(self):
        """ Tests that a wildcard has a default q-factor of 0.0 """
        accept_encoding = 'br;q=0.001, *'
        self.app.config['COMPRESS_ALGORITHM'] = ['gzip', 'br', 'deflate']
        c = Compress(self.app)
        self.assertEqual(c._choose_compress_algorithm(accept_encoding), 'br')


if __name__ == '__main__':
    unittest.main()
