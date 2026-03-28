# Garmin FIT File Battery Checker

A simple Python tool to scan Garmin .fit activity files and extract device battery information.

## Usage

```bash
python3 battery_checker.py <path_to_fit_file>
```

## Example

```bash
python3 battery_checker.py 13_20_January_G_G_w_David.fit
```

## Output

The tool will display:
- All devices found in the activity file
- Device manufacturer and serial number
- Battery voltage (in volts)
- Battery status (Ok, Low, Critical, etc.)
- Battery level percentage (if available)

## Requirements

- Python 3.x
- fitdecode library (included in parent directory)

## Sample Output

```
Found 7 device(s):

Device Index: 3
----------------------------------------
  Manufacturer: garmin
  Serial Number: 3427493824
  Battery Voltage: 2.922 V
  Battery Status: Ok

Device Index: 4
----------------------------------------
  Manufacturer: favero_electronics
  Serial Number: 1479941055
  Battery Voltage: 3.773 V
  Battery Status: Low
```
