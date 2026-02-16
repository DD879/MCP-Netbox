"""
Virtualization Management Tools

This module contains enterprise-grade tools for managing NetBox virtualization objects including
virtual machines, clusters, cluster types, and virtualization platforms.
"""

# Import all virtualization tools to make them discoverable by the registry
from . import clusters
from . import cluster_groups
from . import cluster_types
from . import virtual_machines
from . import vm_interfaces
from . import virtual_disks