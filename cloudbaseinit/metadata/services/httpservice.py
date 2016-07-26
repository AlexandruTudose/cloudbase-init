# Copyright 2012 Cloudbase Solutions Srl
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

import posixpath

import json
from oslo_config import cfg
from oslo_log import log as oslo_logging
from six.moves.urllib import error
from six.moves.urllib import request

from cloudbaseinit.metadata.services import base
from cloudbaseinit.metadata.services import basenetworkservice as service_base
from cloudbaseinit.metadata.services import baseopenstackservice
from cloudbaseinit.utils import network as network_utils

opts = [
    cfg.StrOpt('metadata_base_url', default='http://169.254.169.254/',
               help='The base URL where the service looks for metadata'),
    cfg.BoolOpt('add_metadata_private_ip_route', default=True,
                help='Add a route for the metadata ip address to the gateway'),
]

CONF = cfg.CONF
CONF.register_opts(opts)

LOG = oslo_logging.getLogger(__name__)


class _NetworkDetailsBuilder(service_base.NetworkDetailsBuilder):

    """OpenStack HTTP Service network details builder."""

    _ASSIGNED_TO = "link"
    _MAC_ADDRESS = "ethernet_mac_address"
    _NAME = "id"
    _VERSION = "type"
    _LINKS = "links"
    _NETWORKS = "networks"
    _ROUTES = "routes"
    _IPV4 = "ipv4"

    def __init__(self, service, network_data):
        super(_NetworkDetailsBuilder, self).__init__(service)
        self._network_data = network_data
        self._invalid_links = []

        self._link.update({
            service_base.NAME: self._Field(
                name=service_base.NAME, alias=self._NAME, required=True),
            service_base.MAC_ADDRESS: self._Field(
                name=service_base.MAC_ADDRESS, alias=self._MAC_ADDRESS,
                required=True, on_error=self._on_mac_not_found),
        })
        self._network.update({
            service_base.VERSION: self._Field(
                name=service_base.VERSION, alias=self._VERSION,
                default=4, required=True),
            service_base.ASSIGNED_TO: self._Field(
                name=service_base.ASSIGNED_TO, alias=self._ASSIGNED_TO,
                required=True),
        })

    def _digest_raw_networks(self):
        """Digest the information related to networks."""
        for raw_network in self._network_data.get(self._NETWORKS):
            network = self._get_fields(self._network.values(), raw_network)
            if not network:
                LOG.warning("The network %r does not contains all the "
                            "required fields.", raw_network)
                continue

            self._invalid_links.pop(network[service_base.ASSIGNED_TO], None)
            for raw_route in raw_network.get(self._ROUTES, []):
                raw_route[service_base.ASSIGNED_TO] = network[service_base.ID]
                route = self._get_fields(self._route.values(), raw_route)
                if route:
                    self._routes[route[service_base.ID]] = route
                else:
                    LOG.warning("The route %r does not contains all the "
                                "required fields.", raw_route)

    def _digest(self):
        """Digest the received network information."""
        for raw_link in self._network_data.get(self._LINKS, []):
            link = self._get_fields(self._link.values(), raw_link)
            if link:
                if link[service_base.VERSION] == self._IPV4:
                    link[service_base.VERSION] = service_base.IPV4
                else:
                    link[service_base.VERSION] = service_base.IPV6
                self._links[link[service_base.ID]] = link
            else:
                LOG.warning("The link %r does not contains all the required "
                            "fields.", raw_link)

        self._invalid_links = self._links.keys()
        self._digest_raw_networks()
        while self._invalid_links:
            invalid_link = self._invalid_links.pop()
            LOG.debug("The link %r does not contains any network.")
            self._links.pop(invalid_link)


class HttpService(baseopenstackservice.BaseOpenStackService):

    _POST_PASSWORD_MD_VER = '2013-04-04'
    _NETWORK_DATA_JSON = "openstack/latest/metadata/network_data.json"

    def __init__(self):
        super(HttpService, self).__init__()
        self._enable_retry = True

    def load(self):
        super(HttpService, self).load()
        if CONF.add_metadata_private_ip_route:
            network_utils.check_metadata_ip_route(CONF.metadata_base_url)

        try:
            self._get_meta_data()
            return True
        except Exception:
            LOG.debug('Metadata not found at URL \'%s\'' %
                      CONF.metadata_base_url)
            return False

    def _get_response(self, req):
        try:
            return request.urlopen(req)
        except error.HTTPError as ex:
            if ex.code == 404:
                raise base.NotExistingMetadataException()
            else:
                raise

    def _get_data(self, path):
        norm_path = posixpath.join(CONF.metadata_base_url, path)
        LOG.debug('Getting metadata from: %s', norm_path)
        req = request.Request(norm_path)
        response = self._get_response(req)
        return response.read()

    def _post_data(self, path, data):
        norm_path = posixpath.join(CONF.metadata_base_url, path)
        LOG.debug('Posting metadata to: %s', norm_path)
        req = request.Request(norm_path, data=data)
        self._get_response(req)
        return True

    def _get_password_path(self):
        return 'openstack/%s/password' % self._POST_PASSWORD_MD_VER

    @property
    def can_post_password(self):
        try:
            self._get_meta_data(self._POST_PASSWORD_MD_VER)
            return True
        except base.NotExistingMetadataException:
            return False

    @property
    def is_password_set(self):
        path = self._get_password_path()
        return len(self._get_data(path)) > 0

    def post_password(self, enc_password_b64):
        try:
            path = self._get_password_path()
            action = lambda: self._post_data(path, enc_password_b64)
            return self._exec_with_retry(action)
        except error.HTTPError as ex:
            if ex.code == 409:
                # Password already set
                return False
            else:
                raise

    def _get_network_details_builder(self):
        """Get the required `NetworkDetailsBuilder` object.

        The `NetworkDetailsBuilder` is used in order to create the
        `NetworkDetails` object using the network related information
        exposed by the current metadata provider.
        """
        if not self._network_details_builder:
            network_data = None
            try:
                network_data = self._get_data(self._NETWORK_DATA_JSON)
                network_data = json.loads(network_data)
            except base.NotExistingMetadataException:
                LOG.debug("JSON network metadata not found.")
            except ValueError as exc:
                LOG.error("Failed to load json data: %r" % exc)
            else:
                self._network_details_builder = _NetworkDetailsBuilder(
                    service=self, network_data=network_data)

            if not network_data:
                super(HttpService, self)._get_network_details_builder()

        return self._network_details_builder
