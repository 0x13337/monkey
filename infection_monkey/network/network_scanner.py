import logging
import time

from config import WormConfiguration
from info import local_ips, get_interfaces_ranges
from range import *
from . import HostScanner

__author__ = 'itamar'

LOG = logging.getLogger(__name__)

SCAN_DELAY = 0


class NetworkScanner(object):
    def __init__(self):
        self._ip_addresses = None
        self._ranges = None

    def initialize(self):
        """
        Set up scanning.
        based on configuration: scans local network and/or scans fixed list of IPs/subnets.
        :return:
        """
        # get local ip addresses
        self._ip_addresses = local_ips()

        if not self._ip_addresses:
            raise Exception("Cannot find local IP address for the machine")

        LOG.info("Found local IP addresses of the machine: %r", self._ip_addresses)
        # for fixed range, only scan once.
        self._ranges = [NetworkRange.get_range_obj(address_str=x) for x in WormConfiguration.subnet_scan_list]
        if WormConfiguration.local_network_scan:
            self._ranges += get_interfaces_ranges()
        self._ranges += self._get_inaccessible_subnets_ips()
        LOG.info("Base local networks to scan are: %r", self._ranges)

    def _get_inaccessible_subnets_ips(self):
        subnets_to_scan = []
        for subnet_group in WormConfiguration.inaccessible_subnet_groups:
            for subnet_str in subnet_group:
                if NetworkScanner._is_any_ip_in_subnet([unicode(x) for x in self._ip_addresses], subnet_str):
                    subnets_to_scan += [NetworkRange.get_range_obj(x) for x in subnet_group if x != subnet_str]
                    break
        return subnets_to_scan

    def get_victim_machines(self, scan_type, max_find=5, stop_callback=None):
        assert issubclass(scan_type, HostScanner)

        scanner = scan_type()
        victims_count = 0

        for net_range in self._ranges:
            LOG.debug("Scanning for potential victims in the network %r", net_range)
            for victim in net_range:
                if stop_callback and stop_callback():
                    LOG.debug("Got stop signal")
                    break

                # skip self IP address
                if victim.ip_addr in self._ip_addresses:
                    continue

                # skip IPs marked as blocked
                if victim.ip_addr in WormConfiguration.blocked_ips:
                    LOG.info("Skipping %s due to blacklist" % victim)
                    continue

                LOG.debug("Scanning %r...", victim)

                # if scanner detect machine is up, add it to victims list
                if scanner.is_host_alive(victim):
                    LOG.debug("Found potential victim: %r", victim)
                    victims_count += 1
                    yield victim

                    if victims_count >= max_find:
                        LOG.debug("Found max needed victims (%d), stopping scan", max_find)

                        break

                if SCAN_DELAY:
                    time.sleep(SCAN_DELAY)

    @staticmethod
    def _is_any_ip_in_subnet(ip_addresses, subnet_str):
        for ip_address in ip_addresses:
            if NetworkRange.get_range_obj(subnet_str).is_in_range(ip_address):
                return True
        return False