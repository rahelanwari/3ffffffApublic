# monitor.py
"""
Simple, PEP8-compliant setup script for a future monitoring tool.
- Prompts for hostname, IPv4 address, and a list of metrics.
- Stores everything in memory and prints it in a formatted way.
"""

from dataclasses import dataclass, field
from ipaddress import IPv4Address, AddressValueError
from typing import List


@dataclass
class Target:
    """Represents a system the user wants to monitor."""
    hostname: str
    ip: str
    metrics: List[str] = field(default_factory=list)


def prompt_hostname() -> str:
    """Ask for a non-empty hostname."""
    while True:
        hostname = input("Enter hostname to monitor: ").strip()
        if hostname:
            return hostname
        print("Hostname cannot be empty. Please try again.")


def prompt_ipv4() -> str:
    """Ask for a valid IPv4 address."""
    while True:
        ip_text = input("Enter IPv4 address (e.g., 10.10.30.10): ").strip()
        try:
            # Validate; keep as string for display
            IPv4Address(ip_text)
            return ip_text
        except AddressValueError:
            print("That is not a valid IPv4 address. Please try again.")


def prompt_metrics() -> List[str]:
    """
    Ask for a comma-separated list of metrics.
    Empty input is allowed (results in an empty list).
    """
    print("\nEnter system metrics to track (comma-separated).")
    print("Example: cpu-usage,disk-0-usage,memory-usage\n")
    raw = input("Metrics: ").strip()
    if not raw:
        return []
    # Filter out empties if user types stray commas/spaces
    return [m.strip() for m in raw.split(",") if m.strip()]


def print_summary(target: Target) -> None:
    """Pretty-print the collected information."""
    print("\n=== System Monitor: Summary ===")
    print(f"Hostname : {target.hostname}")
    print(f"IPv4     : {target.ip}")
    if target.metrics:
        print("Metrics  :")
        for m in target.metrics:
            print(f"  - {m}")
    else:
        print("Metrics  : (none provided)")
    print("===============================")


def main() -> None:
    """Main program entry point."""
    print("=== System Monitor Setup ===")
    hostname = prompt_hostname()
    ip_addr = prompt_ipv4()
    metrics = prompt_metrics()

    target = Target(hostname=hostname, ip=ip_addr, metrics=metrics)
    print_summary(target)


if __name__ == "__main__":
    main()
