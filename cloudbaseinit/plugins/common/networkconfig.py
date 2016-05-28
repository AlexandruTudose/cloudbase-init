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

from oslo_log import log as oslo_logging

from cloudbaseinit import exception
from cloudbaseinit.metadata.services import basenetworkservice as service_base
from cloudbaseinit.osutils import factory as osutils_factory
from cloudbaseinit.plugins.common import base as plugin_base


LOG = oslo_logging.getLogger(__name__)


class NetworkConfigPlugin(plugin_base.BasePlugin):

    """Static networking plugin.

    Statically configures each network adapter for which corresponding
    details are found into metadata.
    """

    def __init__(self):
        super(NetworkConfigPlugin, self).__init__()
        self._network_details = None
        self._osutils = osutils_factory.get_os_utils()
        self._adapters = [adapter[1]
                          for adapter in self._osutils.get_network_adapters()]

    def _set_static_network_config_v6(self, link, network):
        """Set IPv6 info for a network card."""

        # TODO(alexcoman): Update the manner of configuring the
        #                  IPV6 networks.
        self._osutils.set_static_network_config_v6(
            mac_address=link.mac_address,
            address6=network.ip_address,
            netmask6=network.netmask,
            gateway6=network.gateway,
        )
        return False

    def _set_static_network_config_v4(self, link, network):
        """Set IPv4 info for a network card."""
        return self._osutils.set_static_network_config(
            mac_address=link.mac_address,
            address=network.ip_address,
            netmask=network.netmask,
            broadcast=network.broadcast,
            gateway=network.gateway,
            dnsnameservers=network.dns_nameservers,
        )

    def _configure_phy(self, link):
        """Configure physical NICs."""
        response = False
        for network_id in self._network_details.get_networks(link.id):
            network = self._network_details.get_network(network_id)
            LOG.debug("Configuring network %(id)r.", {"id": network.id})
            if network.version == service_base.IPV4:
                response |= self._set_static_network_config_v4(link, network)
            else:
                response |= self._set_static_network_config_v6(link, network)
        return response

    def _configure_interface(self, link):
        """Configure different types of interfaces.

        :rtype: bool
        """
        LOG.debug("Configuring link %(name)r: %(mac)s",
                  {"name": link.name, "mac": link.mac_address})
        if link.type == service_base.PHY:
            return self._configure_phy(link)

        raise service_base.NetworkDetailsError("The %r interface type is not"
                                               " supported.", link.type)

    def execute(self, service, shared_data):
        self._network_details = service.get_network_details()
        if not self._network_details:
            LOG.debug("Network information is not available.")
            return plugin_base.PLUGIN_EXECUTION_DONE, False

        if not isinstance(self._network_details, service_base.NetworkDetails):
            raise exception.CloudbaseInitException(
                "Invalid NetworkDetails object {!r} provided."
                .format(type(self._network_details)))

        reboot_required = False
        configured = False
        for link_id in self._network_details.get_links():
            link = self._network_details.get_link(link_id)
            try:
                reboot_required |= self._configure_interface(link)
            except service_base.NetworkDetailsError as exc:
                LOG.exception(exc)
                LOG.error("Failed to configure the interface %r: %s",
                          link.mac_address)
            else:
                configured = True

        if not configured:
            LOG.error("No adapters were configured")

        return plugin_base.PLUGIN_EXECUTION_DONE, reboot_required
