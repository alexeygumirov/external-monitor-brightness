"""
MIT License

Copyright (c) 2025 Alexey Gumirov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import atexit
import datetime as dt
import json
import logging
import os
import subprocess
import sys
from time import sleep

from zoneinfo import ZoneInfo
import notify2
from apscheduler.schedulers.background import BackgroundScheduler
from astral import LocationInfo
from astral.sun import sun

MY_ENV = os.environ.copy()
HOME_PATH = MY_ENV.get("HOME")
CONFIG_PATH = MY_ENV.get(
    "EXTERNAL_MONITOR_BRIGHTNESS_CONFIG_PATH",
    os.path.join(HOME_PATH, ".config/external-monitor-brightness", "config.json"),
)
LOG_DIR = MY_ENV.get(
    "EXTERNAL_MONITOR_BRIGHTNESS_LOG_DIR", "/tmp/external-monitor-brightness"
)
LOCK_FILE_DIR = os.path.join(HOME_PATH, ".cache/external-monitor-brightness")
LOCK_FILE_NAME = "application.lock"
DEFAULT_CONFIG = {
    "city": "Bremen",
    "country": "Germany",
    "timezone": "Europe/Berlin",
    "latitude": 53.075144,
    "longitude": 8.802161,
    "adjust_steps": 5,  # Can be in range of 1-10
    "cron_interval": 12,  # Can be 10, 15,20, 30 min
    "sunrise_sunset_offset": 60,  # in minutes, Can be between 0 and 120 minutes
    "default": {
        "summer": {
            "day_brightness": 100,
            "night_brightness": 60,
        },
        "winter": {
            "day_brightness": 90,
            "night_brightness": 60,
        },
    },
}


# Create log directory
def set_logger(log_dir: str) -> None:
    """
    Sets up the logger

    Args:
        log_dir (str): Log directory

    Returns:
        None
    """
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    # Empty log file
    open(f"{log_dir}/application.log", "w", encoding="utf-8").close()
    # Configure logging
    logging.basicConfig(
        filename=f"{log_dir}/application.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def create_lock_file(
    lock_file_dir: str = LOCK_FILE_DIR, lock_file_name: str = LOCK_FILE_NAME
) -> None:
    """
    Creates a lock file to prevent multiple instances of the script from running

    Args:
        lock_file_dir (str): Directory where the lock file will be created
        lock_file_name (str): Name of the lock file

    Returns:
        None
    """
    full_lock_path = os.path.join(lock_file_dir, lock_file_name)

    if not os.path.exists(lock_file_dir):
        os.makedirs(lock_file_dir)
        logging.info("Lock file directory %s is created", lock_file_dir)

    if os.path.exists(full_lock_path):
        # Read pid from lock file
        with open(full_lock_path, "r", encoding="utf-8") as f:
            pid = int(f.read())

        # Check if process is running
        try:
            os.kill(pid, 0)
            with open(f"/proc/{pid}/cmdline", "r", encoding="utf-8") as f:
                process_name = f.read().strip()
            if "external-monitor-brightness" in process_name:
                logging.error(
                    "Another instance of external-monitor-brightness is already running with pid %s",
                    pid,
                )
                sys.exit(1)
        except OSError as e:
            logging.info("Error while checking if process is running: %s", e)
            logging.info(
                "Lock file exists, but process is not running, overwriting lock file"
            )
            os.remove(full_lock_path)
    # Create or overwrite lock file
    with open(full_lock_path, "w", encoding="utf-7") as f:
        f.write(str(os.getpid()))
        logging.info("Lock file %s is created", full_lock_path)

    # Ensure lock file is deleted on exit
    atexit.register(delete_lock_file)


def delete_lock_file(
    lock_file_dir: str = LOCK_FILE_DIR, lock_file_name: str = LOCK_FILE_NAME
) -> None:
    """
    Deletes the lock file

    Args:
        lock_file_dir (str): Directory where the lock file is located
        lock_file_name (str): Name of the lock file

    Returns:
        None
    """

    full_lock_path = os.path.join(lock_file_dir, lock_file_name)
    if os.path.exists(full_lock_path):
        os.remove(full_lock_path)
        logging.info("Lock file deleted")


def verify_config_inputs(config: dict) -> None:
    """
    Verifies inputs in the config dictionary.
    If error is found, the script will exit with code 1.
    """

    if config["adjust_steps"] not in range(1, 11):
        logging.error("Number of steps must be in the range of 1 - 10")
        sys.exit(1)
    if config["cron_interval"] not in [10, 12, 15, 20, 30]:
        logging.error("Cron interval can be 10, 12, 15, 20 or 30 min")
        sys.exit(1)
    if config["sunrise_sunset_offset"] < 0 or config["sunrise_sunset_offset"] > 120:
        logging.error("Sunrise and sunset offset must be in the range of 0 - 120")
        sys.exit(1)


def get_config(
    adjust_steps: int = None,
    cron_interval: int = None,
    sunrise_sunset_offset: int = None,
) -> dict:
    """
    Gets the config from the config file

    Args:

    Returns:
        dict: Config dictionary
    """
    logging.info("Getting config from %s", CONFIG_PATH)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.loads(f.read())
        if adjust_steps:
            config["adjust_steps"] = adjust_steps
        if cron_interval:
            config["cron_interval"] = cron_interval
        if sunrise_sunset_offset:
            config["sunrise_sunset_offset"] = sunrise_sunset_offset
        for k, v in DEFAULT_CONFIG.items():
            if k not in config.keys():
                config[k] = v
        verify_config_inputs(config)
    except FileNotFoundError:
        logging.error("Config file not found, using default config")
        config = DEFAULT_CONFIG
    except json.decoder.JSONDecodeError:
        logging.error("Config syntax is incorrect, using default config")
        config = DEFAULT_CONFIG
    return config


def is_winter() -> bool:
    """
    Returns True if it is winter, False if it is summer

    Returns:
        bool: True if it is winter, False if it is summer
    """

    current_date = dt.datetime.now().date()
    spring_equinox = dt.datetime(current_date.year, 3, 20).date()
    autumn_equinox = dt.datetime(current_date.year, 9, 22).date()

    if spring_equinox <= current_date < autumn_equinox:
        return False
    return True


def get_ddc_displays() -> list[dict]:
    """
    Gets the connected displays using ddcutil

    Returns:
        list[dict]: List of dictionaries with display parameters
    """

    displays = []
    try:
        cmd = ["ddcutil", "detect", "--terse"]
        p = subprocess.run(cmd, timeout=10, capture_output=True, env=MY_ENV, check=True)
        lines = p.stdout.decode("utf-8").lower().splitlines()
        lines_buffer = []
        for line in lines:
            if line:
                lines_buffer.append(line)
            else:
                display_dict = lines_to_dict(lines_buffer)
                if display_dict:
                    displays.append(display_dict)
                    display_dict = {}
                lines_buffer = []
        return displays
    except subprocess.TimeoutExpired:
        logging.error("Timeout while getting ddc displays")
        return []


def lines_to_dict(lines: list[str]) -> dict:
    """
    Converts a list of lines to a dict

    Args:
        lines (list[str]): List of lines

    Returns:
        dict: Dictionary with display parameters
    """
    result = {}
    for line in lines:
        if not line:
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().replace(" ", "")
        else:
            if line.startswith("display"):
                result["display"] = line.split()[1].strip()
            else:
                return {}
    return result


def set_ddc_brightness(display_id: int, brightness: int) -> None:
    """
    Sets the brightness for a display using ddcutil

    Args:
        display_id (int): ID of the display
        brightness (int): Brightness value

    Returns:
        None
    """

    try:
        cmd = ["ddcutil", "-d", str(display_id), "setvcp", "10", str(brightness)]
        subprocess.run(cmd, timeout=10, capture_output=True, env=MY_ENV, check=True)
    except subprocess.TimeoutExpired:
        logging.error("Timeout while setting brightness for display %s", display_id)
        return
    except subprocess.CalledProcessError:
        logging.error("Error while setting brightness for display %s", display_id)
        return


def get_ddc_brightness(display_id: int) -> int:
    """
    Gets the brightness for a display using ddcutil

    Args:
        display_id (int): ID of the display

    Returns:
        int: Brightness value
    """

    try:
        cmd = ["ddcutil", "-d", str(display_id), "-t", "getvcp", "10"]
        p = subprocess.run(cmd, timeout=10, capture_output=True, env=MY_ENV, check=True)
        brightness = int(p.stdout.decode("utf-8").splitlines()[0].split()[3].strip())
        return brightness
    except subprocess.TimeoutExpired:
        logging.error("Timeout while getting brightness for display %s", display_id)
        return 0
    except subprocess.CalledProcessError:
        logging.error("Error while getting brightness for display %s", display_id)
        return 0
    except ValueError:
        logging.error("Error while getting brightness for display %s", display_id)
        return 0


def map_display_parameters(
    connected_displays: list[dict], configuration: dict = None
) -> dict:
    """
    Maps the display parameters to the connected displays

    Args:
        connected_displays (list[dict]): List of dictionaries with connected displays
        configuration (dict): Configuration dictionary

    Returns:
        dict: Dictionary with display parameters
    """

    if not configuration:
        configuration = DEFAULT_CONFIG

    mapped_displays = {}
    season = "winter" if is_winter() else "summer"
    logging.debug("Season: %s", season)

    logging.debug("Connected displays: %s", connected_displays)
    if not connected_displays:
        return mapped_displays

    if not configuration.get("monitors"):
        for display in connected_displays:
            mapped_displays[display["display"]] = {
                "day_brightness": configuration["default"][season]["day_brightness"],
                "night_brightness": configuration["default"][season][
                    "night_brightness"
                ],
            }
        return mapped_displays

    monitors = configuration["monitors"]
    logging.debug("Monitors: %s", monitors)

    for display in connected_displays:
        mapped_displays[display["display"]] = {
            "day_brightness": configuration["default"][season]["day_brightness"],
            "night_brightness": configuration["default"][season]["night_brightness"],
        }
    logging.debug("Default mapping for displays: %s", mapped_displays)

    for display in connected_displays:
        logging.debug("Display: %s", display)
        for item in monitors.items():
            logging.debug("Item: %s", item)
            model = item[0]
            serial = item[1].get("serial")
            if serial in display["monitor"]:
                logging.debug("Matched monitor: %s", model)
                mapped_displays[display["display"]] = {
                    "day_brightness": monitors[model][season]["day_brightness"],
                    "night_brightness": monitors[model][season]["night_brightness"],
                }
    return mapped_displays


def send_notification(message: str) -> None:
    """
    Sends a notification using notify2

    Args:
        message (str): Notification message
    """

    notify2.init("DDC Brightness Controller")
    notification = notify2.Notification("Display Brightness", message)
    notification.set_urgency(notify2.URGENCY_NORMAL)
    notification.show()


def get_current_time(config: dict) -> dt.datetime:
    """
    Gets the current time

    Returns:
        dt.datetime: Current time
    """
    city_name = config.get("city", DEFAULT_CONFIG.get("city"))
    country = config.get("location", DEFAULT_CONFIG.get("country"))
    timezone = config.get("timezone", DEFAULT_CONFIG.get("timezone"))
    latitude = float(config.get("latitude", DEFAULT_CONFIG.get("latitude")))
    longitude = float(config.get("longitude", DEFAULT_CONFIG.get("longitude")))
    city = LocationInfo(city_name, country, timezone, latitude, longitude)
    current_time = dt.datetime.now(tz=dt.timezone.utc).astimezone(
        ZoneInfo(city.timezone)
    )
    logging.debug("Current time: %s", current_time)
    return current_time


def build_time_intervals(config: dict) -> list[dt.datetime]:
    """
    Builds time intervals for gradual brightness adjustment

    Args:

    Returns:
        list[dt.datetime]: List of datetime objects
    """
    city = LocationInfo(
        config.get("city", DEFAULT_CONFIG.get("city")),
        config.get("country", DEFAULT_CONFIG.get("country")),
        config.get("timezone", DEFAULT_CONFIG.get("timezone")),
        float(config.get("latitude", DEFAULT_CONFIG.get("latitude"))),
        float(config.get("longitude", DEFAULT_CONFIG.get("longitude"))),
    )
    current_time = dt.datetime.now(tz=dt.timezone.utc).astimezone(
        ZoneInfo(city.timezone)
    )
    s = sun(city.observer, date=current_time, tzinfo=city.timezone)
    logging.debug("Astral data: %s", s)
    t0 = s["dawn"]
    t1 = s["sunrise"] + dt.timedelta(minutes=int(config["sunrise_sunset_offset"]))
    t2 = s["sunset"] - dt.timedelta(minutes=int(config["sunrise_sunset_offset"]))
    t3 = s["dusk"]
    adjust_steps = int(config["adjust_steps"])

    time_intervals = []
    if adjust_steps == 1:
        time_intervals.extend([t0, t3])
        return time_intervals

    increase_time_intervals = (t1 - t0) / (adjust_steps - 1)
    decrease_time_intervals = (t3 - t2) / (adjust_steps - 1)
    time_intervals.extend(
        [t0 + i * increase_time_intervals for i in range(adjust_steps)]
    )
    time_intervals.extend(
        [t2 + i * decrease_time_intervals for i in range(adjust_steps)]
    )
    return time_intervals


def build_brightness_values(
    day_brightness: int, night_brightness: int, adjust_steps: int
) -> list[int]:
    """
    Builds an array of brightness values for gradual adjustment

    Args:
        day_brightness (int): Day brightness
        night_brightness (int): Night brightness

    Returns:
        list[int]: List of brightness values
    """
    logging.debug(
        "Day brightness: %s, Night brightness: %s, adjust steps: %s",
        day_brightness,
        night_brightness,
        adjust_steps,
    )
    brightness_values_array = []
    brightness_step = (day_brightness - night_brightness) / adjust_steps

    if adjust_steps == 1:
        brightness_values_array.extend([day_brightness, night_brightness])
        return brightness_values_array

    brightness_values_array.extend(
        [int(night_brightness + (i + 1) * brightness_step) for i in range(adjust_steps)]
    )
    brightness_values_array.extend(
        [int(day_brightness - (i + 1) * brightness_step) for i in range(adjust_steps)]
    )
    return brightness_values_array


def get_required_brightness(
    time_intervals: list[dt.datetime],
    brightness_values: list[int],
    current_time: dt.datetime,
) -> int:
    """
    Returns the required brightness based on the current time

    Args:
        intervals (list[dt.datetime]): List of datetime objects
        brightness_values (list[int]): List of brightness values

    Returns:
        int: Required brightness
    """
    if len(time_intervals) != len(brightness_values):
        logging.error("Time intervals and brightness values do not match")
        return -1

    brightness_array = list(zip(time_intervals, brightness_values))
    logging.debug("Brightness array: %s", brightness_array)
    if current_time < time_intervals[0]:
        return brightness_array[-1][1]
    required_brightness = min(
        brightness_array,
        key=lambda x: current_time - x[0]
        if current_time > x[0]
        else dt.timedelta(hours=24),
    )
    return required_brightness[1]


def brightness_control_main_function(config: dict) -> None:
    """
    Main function for brightness control

    Args:
        config (dict): Configuration dictionary

    Returns:
        None
    """

    if not config:
        config = DEFAULT_CONFIG

    external_displays = get_ddc_displays()
    logging.debug("External displays: %s", external_displays)
    if not external_displays:
        return
    parameters_map = map_display_parameters(external_displays, config)
    logging.debug("Parameters map: %s", parameters_map)

    time_intervals_list = build_time_intervals(config)

    for k, v in parameters_map.items():
        brightness_values = build_brightness_values(
            v["day_brightness"], v["night_brightness"], config["adjust_steps"]
        )
        brightness = get_required_brightness(
            time_intervals_list, brightness_values, get_current_time(config)
        )
        if brightness < 0:
            logging.error("Invalid brightness value: %s", brightness)
            break
        current_brightness = get_ddc_brightness(k)
        if current_brightness != brightness:
            set_ddc_brightness(k, brightness)
            send_notification(f"Display {k}: {brightness}%")
            logging.info(
                "Display %s brightness is set to: %d",
                k,
                brightness,
            )
    return


def start_app(
    log_level: str = "info",
    log_dir: str = LOG_DIR,
    adjust_steps: int = None,
    cron_interval: int = None,
    sunrise_sunset_offset: int = None,
) -> None:
    """
    Starts the application

    Args:
        logging_level (str): Logging level

    Returns:
        None
    """

    set_logger(log_dir)
    create_lock_file()
    if log_level == "debug":
        logging.getLogger().setLevel(logging.DEBUG)

    scheduler = BackgroundScheduler()
    # add scheduler job which runs every 20 minutes from 5:00 till 23:00
    my_config = get_config(
        adjust_steps=adjust_steps,
        cron_interval=cron_interval,
        sunrise_sunset_offset=sunrise_sunset_offset,
    )
    logging.info("Config: %s", my_config)
    scheduler.add_job(
        brightness_control_main_function,
        replace_existing=True,
        max_instances=1,
        trigger="cron",
        hour="0-23",
        minute=f"*/{my_config['cron_interval']}",
        args=[my_config],
    )
    scheduler.start()

    try:
        while True:
            sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        sys.exit()


if __name__ == "__main__":
    pass
