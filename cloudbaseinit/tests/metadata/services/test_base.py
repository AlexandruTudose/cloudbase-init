# Copyright 2015 Cloudbase Solutions Srl
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import unittest
try:
    import unittest.mock as mock
except ImportError:
    import mock

from cloudbaseinit.metadata.services import base


class FakeService(base.BaseMetadataService):
    def _get_data(self):
        return (b'\x1f\x8b\x08\x00\x93\x90\xf2U\x02'
                b'\xff\xcbOSH\xce/-*NU\xc8,Q(\xcf/\xca.'
                b'\x06\x00\x12:\xf6a\x12\x00\x00\x00')

    def get_user_data(self):
        return self._get_data()


class FakeAdaptor(base.BaseNetworkAdapter):

    def __init__(self, service):
        super(FakeAdaptor, self).__init__(service=service)
        self._links = {
            mock.sentinel.link1: {
                base.NAME: mock.sentinel.name,
                base.MAC_ADDRESS: mock.sentinel.mac,
            },
            mock.sentinel.link2: {
                base.NAME: mock.sentinel.name,
                base.MAC_ADDRESS: mock.sentinel.mac,
            },
        }
        self._networks = {
            mock.sentinel.net1: {
                base.NAME: mock.sentinel.net1,
                base.IP_ADDRESS: mock.sentinel.address4,
                base.VERSION: 4,
            },
            mock.sentinel.net2: {
                base.NAME: mock.sentinel.net2,
                base.IP_ADDRESS: mock.sentinel.address6,
                base.VERSION: 6,
            }
        }

    def get_link(self, name):
        """Return all the information related to the link."""
        return self._links[name]

    def get_links(self):
        """Return a list with the names of the available links."""
        return self._links.keys()

    def get_network(self, link, name):
        """Return all the information related to the network."""
        return self._networks[name]

    def get_networks(self, link):
        """Returns all the network names bound by the required link."""
        return self._networks.keys()


class TestBase(unittest.TestCase):

    def setUp(self):
        self._service = FakeService()

    def test_get_decoded_user_data(self):
        userdata = self._service.get_decoded_user_data()
        self.assertEqual(b"of course it works", userdata)

    def test_get_network_details(self):
        # TODO(stefan-caraiman): Add this test.
        pass


class TestAdaptor(unittest.TestCase):

    def setUp(self):
        self._adaptor = FakeAdaptor(mock.sentinel.service)

    def test_digest_interface(self):
        # TODO(stefan-caraiman): Add this test.
        pass

    def test_get_field(self):
        # TODO(stefan-caraiman): Add this test.
        pass

    def test_get_fields(self):
        # TODO(stefan-caraiman): Add this test.
        pass

    def test_get_link(self):
        # TODO(stefan-caraiman): Add this test.
        pass

    def test_get_links(self):
        # TODO(stefan-caraiman): Add this test.
        pass

    def test_get_network(self):
        # TODO(stefan-caraiman): Add this test.
        pass

    def test_get_networks(self):
        # TODO(stefan-caraiman): Add this test.
        pass


class TestNetworkConfig(unittest.TestCase):

    def setUp(self):
        self._config = base.NetworkConfig(mock.sentinel.network_adapter)

    def test_get_networks(self):
        # TODO(stefan-caraiman): Add this test.
        pass

    def test_digest(self):
        # TODO(stefan-caraiman): Add this test.
        pass

    def test_get_network_details(self):
        # TODO(stefan-caraiman): Add this test.
        pass
