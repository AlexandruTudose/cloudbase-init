# Copyright 2014 Cloudbase Solutions Srl
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

from cloudbaseinit.tests.metadata import fake_json_response
from cloudbaseinit.tests import testutils
from cloudbaseinit.utils import debiface


class TestInterfacesParser(unittest.TestCase):

    def setUp(self):
        date = "2013-04-04"
        content = fake_json_response.get_fake_metadata_json(date)
        self.data = content["network_config"]["debian_config"]

    def _test_parse_nics(self, no_nics=False):
        with testutils.LogSnatcher('cloudbaseinit.utils.'
                                   'debiface') as snatcher:
            nics = [nic for nic in debiface.parse(self.data)]

        if no_nics:
            expected_logging = 'Invalid Debian config to parse:'
            self.assertTrue(snatcher.output[0].startswith(expected_logging))
            self.assertFalse(nics)
            return
        # check what we've got
        nic0 = {
            debiface.NAME: fake_json_response.NAME0,
            debiface.MAC: fake_json_response.MAC0.upper(),
            debiface.ADDRESS: fake_json_response.ADDRESS0,
            debiface.ADDRESS6: fake_json_response.ADDRESS60,
            debiface.NETMASK: fake_json_response.NETMASK0,
            debiface.NETMASK6: fake_json_response.NETMASK60,
            debiface.BROADCAST: fake_json_response.BROADCAST0,
            debiface.GATEWAY: fake_json_response.GATEWAY0,
            debiface.GATEWAY6: fake_json_response.GATEWAY60,
            debiface.DNSNS: fake_json_response.DNSNS0.split(),
        }
        nic1 = {
            debiface.NAME: fake_json_response.NAME1,
            debiface.MAC: None,
            debiface.ADDRESS: fake_json_response.ADDRESS1,
            debiface.ADDRESS6: fake_json_response.ADDRESS61,
            debiface.NETMASK: fake_json_response.NETMASK1,
            debiface.NETMASK6: fake_json_response.NETMASK61,
            debiface.BROADCAST: fake_json_response.BROADCAST1,
            debiface.GATEWAY: fake_json_response.GATEWAY1,
            debiface.GATEWAY6: fake_json_response.GATEWAY61,
            debiface.DNSNS: None,
        }
        self.assertEqual([nic0, nic1], nics)

    def test_nothing_to_parse(self):
        invalid = [None, "", 324242, ("dasd", "dsa")]
        for data in invalid:
            self.data = data
            self._test_parse_nics(no_nics=True)

    def test_parse(self):
        self._test_parse_nics()
