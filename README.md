# External Monitor Brightness Controller

This Python application is designed to automatically adjust the brightness of external monitors connected to a Linux machine based on the time of day and seasonal changes. It utilizes the [`ddcutil`](https://www.ddcutil.com/) tool to communicate with the monitors via the Display Data Channel (DDC) protocol.

The application reads the dawn, sunrise, dusk and sunset times for a specified location and adjusts the brightness of the connected monitors gradually:
 - from dusk till down the brightness is set to the night value (default 60%)
 - from dawn till sunrise the brightness is set to the night value + 1/3 * difference between day and night values. E.g. if day value is 100% and night value is 60% the brightness will be set to 73.33%.
 - from sunrise till (sunrise + 1 hour) the brightness is set to the night value + 2/3 * difference between day and night values. E.g. if day value is 100% and night value is 60% the brightness will be set to 86.67%.
 - from (sunrise + 1 hour) till (sunset - 1 hour) the brightness is set to the day value.
 - from (sunset - 1 hour) till sunset the brightness is set to the night value + 2/3 * difference between day and night values. E.g. if day value is 100% and night value is 60% the brightness will be set to 86.67%.
 - from sunset till dusk the brightness is set to the night value + 1/3 * difference between day and night values. E.g. if day value is 100% and night value is 60% the brightness will be set to 73.33%.
 - from dusk till dawn the brightness is set to the night value (default 60%).

The image below shows the brightness levels for the day with the dawn at 05:55:00, sunrise at 06:32:00, sunset at 16:09:00 and dusk at 16:46:00.
![Brightness levels](./images/brightness_chart.png)

The astral times for a given location (in the `config.json` file) are taken fro the [astral](hhttps://astral.readthedocs.io/en/latest/) library. Therefore no internet connection is needed for this application.

This tool does not work with built-in laptop displays, because ususally their brightness is controlled by the laptop's hardware, and not by the DDC protocol.

## Key Functionality

- Automatically adjusts the brightness of connected external monitors based on the time of day and season (summer/winter).
- Supports custom brightness settings for specific monitor models and serial numbers.
- Sends desktop notifications when the brightness is adjusted.
- Runs as a background process, controlled by the `APScheduler` library.
- Prevents multiple instances of the application from running simultaneously.

## Dependencies

- Python 3.11, 3.12, or 3.13
- `ddcutil` (available in most Linux distributions):
    - `ddcutil` web-site: [https://www.ddcutil.com/](https://www.ddcutil.com/)
- Python packages:
  - `notify2`
  - `APScheduler`
  - `astral`
  - `zoneinfo`

## Installation

1. Clone the repository or download the source code.
2. Navigate to the project directory.
3. Make the installation script executable and run it.

```bash
./install.sh
```

This script will create a virtual environment, install the required Python packages, and create a symbolic link to the application executable in your `~/.local/bin` directory (or `/usr/local/bin` on macOS).

**Note:** You can optionally provide the `-p` flag to specify a custom path for the virtual environment:

```bash
./install.sh -p /path/to/venv
```

## Configuration

The application uses a configuration file located at `~/.config/external-monitor-brightness/config.json`. If the file does not exist, the application will use default settings.

The configuration file should have the following structure:

```json
{
  "city": "City Name",
  "location": "Country",
  "timezone": "Continent/City",
  "latitude": 50.7014831,
  "longitude": 7.1645746,
  "monitors": {
    "Monitor Model 1": {
      "serial": "Monitor Serial Number",
      "summer": {
        "day_brightness": 100,
        "night_brightness": 60
      },
      "winter": {
        "day_brightness": 90,
        "night_brightness": 60
      }
    }
  },
  "default": {
    "summer": {
      "day_brightness": 100,
      "night_brightness": 60
    },
    "winter": {
      "day_brightness": 90,
      "night_brightness": 60
    }
  }
}
```

- `city`, `location`, `timezone`, `latitude`, and `longitude` are used to determine the sunrise and sunset times.
- `default` contains the default brightness settings for monitors not listed in the `monitors` section.
- `monitors` (optional) contains specific brightness settings for individual monitor models and serial numbers. If not specified, the default settings will be used.
    - To list your monitors, run `ddcutil detect --terse`.

## Usage

After installation, you can run the application with the following command (put it in the background):

```bash
external-monitor-brightness &
```

I recommend adding this command to your startup applications to ensure the application starts automatically when you log in.
If you are using a desktop environment that supports systemd services, you can create a systemd service file to manage the application.

By default, the application will run in the background (the dedicated cron job is created) and adjust the monitor brightness every 15 minutes between 5:00 AM and 11:00 PM.

## Options

- `-v, --version`: Display the application version.
- `-vv, --verbose`: Enable verbose logging. (loging level is set to DEBUG)
- `-l, --log-directory`: Specify the directory for the application logs. (default: `/tmp/external-monitor-brightness`)

### Environment variables

- `EXTERNAL_MONITOR_BRIGHTNESS_CONFIG_PATH`: Specify the path to the configuration file. (default: `~/.config/external-monitor-brightness/config.json`)
- `EXTERNAL_MONITOR_BRIGHTNESS_LOG_DIR`: Specify the directory for the application logs. (default: `/tmp/external-monitor-brightness`)

## Logs

The application logs can be found in the `/tmp/external-monitor-brightness/application.log` file.

## Uninstallation

To uninstall the application, follow these steps:

1. Remove the symbolic link from `~/.local/bin`

```bash
rm ~/.local/bin/external-monitor-brightness
```

2. Remove the virtual environment directory (if you used the default path):

```bash
rm -rf ~/.local/virtualenv/external-monitor-brightness
```

3. Remove the configuration directory:

```bash
rm -rf ~/.config/external-monitor-brightness
```

## Contributing

Contributions are welcome! If you find any issues or have suggestions for improvements, please open an issue or submit a pull request.

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

Copyright (c) 2025 Alexey Gumirov
