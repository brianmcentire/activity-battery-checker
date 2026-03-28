#!/usr/bin/env python3
"""
Garmin FIT File Battery Checker
Scans activity files and identifies all devices with their battery/power levels

CLI wrapper around battery_parser.py shared parsing logic.
"""

import sys
import os
import argparse

from battery_parser import (
    parse_fit_file,
    get_garmin_product_name,
    get_device_type_name,
    format_battery_status,
    is_battery_ok,
    ParseResult,
    DeviceInfo,
)


def print_device_info_brief(result: ParseResult, problems_only=False):
    """Print brief battery information - one line per device with battery info."""
    output = []

    for device in result.devices:
        if not device.has_battery_info:
            continue

        if problems_only and is_battery_ok(device):
            continue

        status_parts = []
        if device.battery_status is not None:
            status_parts.append(device.battery_status.capitalize())
        if device.battery_voltage is not None:
            status_parts.append(f"{device.battery_voltage:.2f}V")
        if device.battery_level is not None:
            status_parts.append(f"{device.battery_level}%")

        status_str = ", ".join(status_parts) if status_parts else "Unknown"
        output.append((device.device_name, status_str))

    if not output:
        if not problems_only:
            print("No devices with battery information found.")
    else:
        for device_name, status in output:
            print(f"{device_name}: {status}")


def print_device_info_verbose(result: ParseResult):
    """Print detailed device information."""
    if not result.devices:
        print("No devices found in the FIT file.")
        return

    print(f"\nFound {result.total_devices} device(s):\n")
    print("=" * 80)

    for device in result.devices:
        print(f"\nDevice Index: {device.device_index}")
        print("-" * 40)

        # Device classification
        if device.classification != 'unknown':
            print(f"  Device: {device.classification.replace('_', ' ').title()}")

        if device.manufacturer:
            print(f"  Manufacturer: {device.manufacturer}")

        if device.product:
            print(f"  Product: {device.product}")
        elif device.product_id:
            print(f"  Product ID: {device.product_id}")

        if device.serial_number:
            print(f"  Serial Number: {device.serial_number}")

        # Battery information
        has_battery_info = False
        if device.battery_voltage is not None:
            print(f"  Battery Voltage: {device.battery_voltage:.3f} V")
            has_battery_info = True
        if device.battery_status is not None:
            print(f"  Battery Status: {device.battery_status.capitalize()}")
            has_battery_info = True
        if device.battery_level is not None:
            print(f"  Battery Level: {device.battery_level}%")
            has_battery_info = True

        if not has_battery_info:
            print("  Battery Info: Not available")

    print("\n" + "=" * 80)

    # Summary
    print("\nSUMMARY:")
    print("-" * 40)
    print(f"Total devices: {result.total_devices}")
    print(f"Devices with battery info: {result.devices_with_battery}")
    print("=" * 80)


def print_device_info(result: ParseResult, verbose=False, problems_only=False):
    """Print device information in the requested format."""
    if verbose:
        print_device_info_verbose(result)
    else:
        print_device_info_brief(result, problems_only=problems_only)


def main():
    parser = argparse.ArgumentParser(
        description='Scan Garmin FIT files for device battery information',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s activity.fit              # Show all devices with battery info
  %(prog)s activity.fit --brief      # Show only devices with battery problems (silent if all OK)
  %(prog)s activity.fit --verbose    # Detailed output (all devices)
  %(prog)s activity.fit -v           # Same as --verbose
        """
    )
    parser.add_argument('filepath', help='Path to the .fit file')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Show detailed information for all devices')
    parser.add_argument('-b', '--brief', action='store_true',
                       help='Show only devices with battery problems (silent if all OK)')

    args = parser.parse_args()

    if not os.path.exists(args.filepath):
        print(f"Error: File '{args.filepath}' not found.")
        sys.exit(1)

    if args.verbose:
        print(f"Scanning FIT file: {args.filepath}")

    result = parse_fit_file(args.filepath)

    if result.success:
        print_device_info(result, verbose=args.verbose, problems_only=args.brief)
    else:
        print(f"Failed to scan FIT file: {result.error}")
        sys.exit(1)


if __name__ == '__main__':
    main()
