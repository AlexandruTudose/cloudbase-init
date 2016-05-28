# Copyright 2016 Cloudbase Solutions Srl
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

"""Network Metadata Services base-classes.

(Beginning of) the contract that metadata services which expose network
information and parsers must follow.
"""

import abc
import collections
import uuid

import ipaddress
from oslo_log import log as oslo_logging
import six

from cloudbaseinit.metadata.services import base
from cloudbaseinit.osutils import factory as osutils_factory

LOG = oslo_logging.getLogger(__name__)

# Network types
IPV4 = 4
IPV6 = 6

# Different types of interfaces
PHY = "phy"
BOND = "bond"
VIF = "vif"

# Field names related to network configuration
ASSIGNED_TO = "assigned_to"
BOND_LINKS = "bond_links"
BOND_MODE = "bond_mode"
BROADCAST = "broadcast"
DNS = "dns_nameservers"
GATEWAY = "gateway"
ID = "id"
IP_ADDRESS = "ip_address"
NAME = "name"
MAC_ADDRESS = "mac_address"
MTU = "mtu"
NETMASK = "netmask"
TYPE = "type"
VERSION = "version"
VLAN_ID = "vlan_id"
VLAN_LINK = "vlan_link"


class NetworkDetailsError(Exception):

    """Base exception for all the network data processing related errors."""
    pass


class NetworkDetails(object):

    """Container for network information.

    .. note ::
        Both the custom service(s) and the networking plugin
        should know about the entries of these kind of objects.
    """

    def __init__(self, raw_links, raw_networks, raw_references):
        self._assigned_to = raw_links
        self._links = raw_networks
        self._networks = raw_references

    def get_link(self, link_id):
        """Return all the available information related to the received link.

        :rtype: collection.namedtuple

        .. note ::
            The link namedtuple contains the following fields: `id`, `name`,
            `type`, `mac_address`, `mtu`, `bond_links`, `bond_mode`,
            `vlan_id` and `vlan_link`.
        """
        return self._links.get(link_id)

    def get_links(self):
        """Return a list with the ids of the available links.

        :rtype: list
        """
        return self._links.keys()

    def get_network(self, network_id):
        """Return all the information related to the received network.

        :rtype: collection.namedtuple

        .. note ::
            The link namedtuple contains the following fields: `id`,
            `ip_address`, `version`, `netmask`, `gateway`, `broadcast`,
            `dns_nameservers` and `assigned_to`.
        """
        return self._networks.get(network_id)

    def get_networks(self, link_id):
        """Returns all the network ids assigned to the required link.

        :rtype: list
        """
        return self._assigned_to.get(link_id)


@six.add_metaclass(abc.ABCMeta)
class NetworkDetailsBuilder(object):

    """The contract class for all the network details builders.

    Build the `NetworkDetails` object using the network information
    available in service specific format in order to be easily consumed
    by the network plugin.
    """

    _Link = collections.namedtuple("Link", [ID, NAME, TYPE, MAC_ADDRESS, MTU,
                                            BOND_LINKS, BOND_MODE, VLAN_ID,
                                            VLAN_LINK])

    _Network = collections.namedtuple("Network", [ID, IP_ADDRESS, VERSION,
                                                  NETMASK, GATEWAY, BROADCAST,
                                                  DNS, ASSIGNED_TO])

    class _Field(collections.namedtuple("Field", ["name", "alias", "default",
                                                  "required", "on_error"])):

        """Container for meta information regarding network data.

        :param name:     The name of the current piece of information.
        :param alias:    A list of alternative names of the current piece of
                         information (default: `None`).
        :param default:  If this information is not required a default value
                         can be provided (default: `None`)
        :param required: Whether the current piece of information is required
                         for the `NetworkDetails` object or can be missing.
                         (default: `True`)
        :param on_error: A method that will be called when the current field
                         is missing from the raw data.
                         The builder will pass to the `on_error` callback the
                         raw_data and also a reference to the processed data.
                         If the `on_error` method will return `False` the
                         execution of the `get_fields` will be stopped.
        """

        __slots__ = ()

        def __new__(cls, name, alias=None, default=None, required=False,
                    on_error=None):
            return super(cls, cls).__new__(cls, name, alias, default,
                                           required, on_error)

    def __init__(self, service):
        self._service = service
        self._networks = {}
        self._links = {}
        osutils = osutils_factory.get_os_utils()
        self._network_adapters = osutils.get_network_adapters()

        self._link = {
            ID: self._Field(name=ID, default=lambda: str(uuid.uuid1())),
            NAME: self._Field(name=NAME, required=True),
            MAC_ADDRESS: self._Field(name=MAC_ADDRESS, required=True,
                                     on_error=self._on_mac_not_found),
            TYPE: self._Field(name=TYPE, default=PHY, required=False),
            MTU: self._Field(name=MTU, required=False),
            BOND_LINKS: self._Field(name=BOND_LINKS, required=False),
            BOND_MODE: self._Field(name=BOND_MODE, required=False),
            VLAN_ID: self._Field(name=VLAN_ID, required=False),
            VLAN_LINK: self._Field(name=VLAN_LINK, required=False),
        }
        self._network = {
            ID: self._Field(name=ID, default=lambda: str(uuid.uuid1())),
            IP_ADDRESS: self._Field(name=IP_ADDRESS, required=True),
            VERSION: self._Field(name=VERSION, default=4, required=False),
            NETMASK: self._Field(name=NETMASK, required=True),
            GATEWAY: self._Field(name=GATEWAY, required=True),
            BROADCAST: self._Field(name=BROADCAST, required=False),
            DNS: self._Field(name=DNS, default=[], required=False),
            ASSIGNED_TO: self._Field(name=ASSIGNED_TO, required=False),
        }

    @staticmethod
    def _digest_interface(ip_address, netmask=None):
        """Digest the information related to the current interface."""
        if netmask:
            ip_address = six.u("%s/%s") % (ip_address, netmask)

        ip_interface = ipaddress.ip_interface(ip_address)
        return {
            BROADCAST: str(ip_interface.network.broadcast_address),
            NETMASK: str(ip_interface.netmask),
            IP_ADDRESS: str(ip_interface.ip),
            VERSION: int(ip_interface.version)
        }

    @staticmethod
    def _get_field(field, raw_data):
        """Find the required information in the raw data."""
        aliases = [field.name]
        if isinstance(field.alias, six.string_types):
            aliases.append(field.alias)
        elif isinstance(field.alias, (list, tuple)):
            aliases.extend(field.alias)

        for alias in aliases:
            if alias in raw_data:
                return field.name, raw_data[alias]

        if not field.required:
            if six.callable(field.default):
                return field.name, field.default()
            else:
                return field.name, field.default

        raise NetworkDetailsError("The required field %(field)r is missing." %
                                  {"field": field.name})

    def _get_fields(self, fields, raw_data):
        """Get the received fields from the raw data.

        Get all the required information related to all the received
        fields if it is posible.
        """
        data = {}
        for field in fields:
            try:
                field_name, field_value = self._get_field(field, raw_data)
                data[field_name] = field_value
            except NetworkDetailsError as reason:
                LOG.warning("Failed to process %(data)r: %(reason)s",
                            {"data": raw_data, "reason": reason})
                if six.callable(field.on_error):
                    LOG.debug("Running on_error callback for field %r.",
                              field.name)
                    if field.on_error(raw_data, data):
                        continue
                return
        return data

    def _on_mac_not_found(self, raw_data, output):
        """Handle the scenario where the mac address is missing from raw data.

        Check the raw data in order to find some pice of information that
        may help to fill the missing data if possible.

        :rtype: bool
        """
        try:
            name = self._get_field(self._link[NAME], raw_data)
        except NetworkDetailsError:
            LOG.debug("Failed to get the link name.")
            return False

        LOG.debug("Trying to find the MAC address using link name.")
        for addapter_name, mac_address in self._network_adapters:
            if addapter_name == name:
                LOG.debug("The MAC address for the current link was found.")
                output[MAC_ADDRESS] = mac_address
                return True

        LOG.debug("The link name %r is not present in the network adapters"
                  " information %r." % name, self._network_adapters)
        return False

    def _digest_links(self):
        """Process raw data regarding the links."""
        links = {}
        for raw_link in self._links:
            raw_link.update(self._digest_interface(raw_link[IP_ADDRESS],
                                                   raw_link[NETMASK]))
            try:
                link = self._Link(**raw_link)
            except TypeError as exc:
                LOG.debug("Failed to process raw link %(link)r: %(reason)s",
                          {"link": raw_link, "reason": exc})
                raise NetworkDetailsError("Invalid raw link %r provied." %
                                          raw_link)
            else:
                links[link.id] = link
        return links

    def _digest_networks(self):
        """Process raw data regarding the networks."""
        networks = {}
        references = {}
        for raw_network in self._networks:
            try:
                network = self._Network(**raw_network)
            except TypeError as exc:
                LOG.debug("Failed to process raw network %(network)r: "
                          "%(exc)s", {"network": raw_network, "exc": exc})
                raise NetworkDetailsError("Invalid raw network %r provied." %
                                          raw_network)
            else:
                networks[network.id] = network
                assigned_to = references.setdefault(
                    network.assigned_to, [])
                assigned_to.append(network.id)
        return networks, references

    @abc.abstractmethod
    def _digest(self):
        """Digest the received network information."""
        pass

    def get_network_details(self):
        """Create a `NetworkDetails` object using available information."""
        if not self._links or not self._networks:
            self._digest()

        links = self._digest_links()
        networks, references = self._digest_networks()

        return NetworkDetails(raw_links=links, raw_networks=networks,
                              raw_references=references)


@six.add_metaclass(abc.ABCMeta)
class BaseNetworkMetadataService(base.BaseMetadataService):

    """Base class for all metadata services which expose network information.

    Process the network information provided in the service specific
    format to a format that can be easily procesed by cloudbase-init
    plugins.
    """

    def __init__(self):
        super(BaseNetworkMetadataService, self).__init__()
        self._network_details_builder = None

    @abc.abstractmethod
    def _get_data(self, path):
        """Getting the required information ussing metadata service."""
        pass

    @abc.abstractmethod
    def _get_network_details_builder(self):
        """Get the required `NetworkDetailsBuilder` object.

        The `NetworkDetailsBuilder` is used in order to create the
        `NetworkDetails` object using the network related information
        exposed by the current metadata provider.
        """
        pass

    def get_network_details(self):
        """Return a list of `NetworkDetails` objects.

        These objects provide details regarding static
        network configuration.
        """
        builder = self._get_network_details_builder()
        if builder:
            return builder.get_network_details()
