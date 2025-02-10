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

import notify2
from apscheduler.schedulers.background import BackgroundScheduler
from astral import LocationInfo
from astral.sun import sun
from zoneinfo import ZoneInfo

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


def get_config() -> dict:
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
    connected_displays: list[dict], configuration: dict = DEFAULT_CONFIG
) -> dict:
    """
    Maps the display parameters to the connected displays

    Args:
        connected_displays (list[dict]): List of dictionaries with connected displays
        configuration (dict): Configuration dictionary

    Returns:
        dict: Dictionary with display parameters
    """
    mapped_displays = {}
    season = "winter" if is_winter() else "summer"
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
    for model in monitors.keys():
        for display in connected_displays:
            if (
                model in display["monitor"]
                and monitors[model]["serial"] in display["monitor"]
            ):
                mapped_displays[display["display"]] = {
                    "day_brightness": monitors[model][season]["day_brightness"],
                    "night_brightness": monitors[model][season]["night_brightness"],
                }
            else:
                mapped_displays[display["display"]] = {
                    "day_brightness": configuration["default"][season][
                        "day_brightness"
                    ],
                    "night_brightness": configuration["default"][season][
                        "night_brightness"
                    ],
                }

        return mapped_displays


def send_notification(message: str) -> None:
    """
    Sends a notification using notify2

    Args:
        message (str): Notification message
    """

    notify2.init("DDC Brightness Controller")
    notification = notify2.Notification("DDC Brightness", message)
    notification.set_urgency(notify2.URGENCY_NORMAL)
    notification.show()


def brightness_control_main_function(config: dict = DEFAULT_CONFIG) -> None:
    """
    Main function for brightness control

    Args:
        config (dict): Configuration dictionary

    Returns:
        None
    """
    city_name = config.get("city", DEFAULT_CONFIG.get("city"))
    country = config.get("location", DEFAULT_CONFIG.get("country"))
    timezone = config.get("timezone", DEFAULT_CONFIG.get("timezone"))
    latitude = float(config.get("latitude", DEFAULT_CONFIG.get("latitude")))
    longitude = float(config.get("longitude", DEFAULT_CONFIG.get("longitude")))

    logging.info("City: %s, Country: %s, Timezone: %s", city_name, country, timezone)

    city = LocationInfo(city_name, country, timezone, latitude, longitude)

    current_time = dt.datetime.now(tz=dt.timezone.utc).astimezone(
        ZoneInfo(city.timezone)
    )
    s = sun(city.observer, date=current_time, tzinfo=city.timezone)
    external_displays = get_ddc_displays()
    if not external_displays:
        return
    parameters_map = map_display_parameters(external_displays, config)

    if current_time < s["dawn"]:
        for display, params in parameters_map:
            brightness = params["night_brightness"]
            current_brightness = get_ddc_brightness(display)
            if current_brightness != brightness:
                set_ddc_brightness(display, brightness)
                send_notification(f"Night mode: {brightness}")
                logging.info("Night mode. Brightness is set to: %d", brightness)
        return

    if s["dawn"] <= current_time < s["sunrise"]:
        for display, params in parameters_map.items():
            brightness = (
                params["night_brightness"]
                + (params["day_brightness"] - params["night_brightness"]) // 3
            )
            current_brightness = get_ddc_brightness(display)
            if current_brightness != brightness:
                set_ddc_brightness(display, brightness)
                send_notification(f"Morning mode: {brightness}")
                logging.info("Morning mode. Brightness is set to: %d", brightness)
        return

    if s["sunrise"] <= current_time < s["sunrise"] + dt.timedelta(hours=1):
        for display, params in parameters_map.items():
            brightness = (
                params["day_brightness"]
                - (params["day_brightness"] - params["night_brightness"]) // 3
            )
            current_brightness = get_ddc_brightness(display)
            if current_brightness != brightness:
                set_ddc_brightness(display, brightness)
                send_notification(f"Morning mode: {brightness}")
                logging.info("Morning mode. Brightness is set to: %d", brightness)
        return

    if (
        s["sunrise"] + dt.timedelta(hours=1)
        <= current_time
        < s["sunset"] - dt.timedelta(hours=1)
    ):
        for display, params in parameters_map.items():
            brightness = params["day_brightness"]
            current_brightness = get_ddc_brightness(display)
            if current_brightness != brightness:
                set_ddc_brightness(display, brightness)
                send_notification(f"Day mode: {brightness}")
                logging.info("Day mode. Brightness is set to: %d", brightness)
        return

    if s["sunset"] - dt.timedelta(hours=1) <= current_time < s["sunset"]:
        for display, params in parameters_map.items():
            brightness = (
                params["day_brightness"]
                - (params["day_brightness"] - params["night_brightness"]) // 3
            )
            current_brightness = get_ddc_brightness(display)
            if current_brightness != brightness:
                set_ddc_brightness(display, brightness)
                send_notification(f"Evening mode: {brightness}")
                logging.info("Evening mode. Brightness is set to: %d", brightness)
        return

    if s["sunset"] <= current_time < s["dusk"]:
        for display, params in parameters_map.items():
            brightness = (
                params["night_brightness"]
                + (params["day_brightness"] - params["night_brightness"]) // 3
            )
            current_brightness = get_ddc_brightness(display)
            if current_brightness != brightness:
                set_ddc_brightness(display, brightness)
                send_notification(f"Evening mode: {brightness}")
                logging.info("Evening mode. Brightness is set to: %d", brightness)
        return

    if s["dusk"] <= current_time:
        for display, params in parameters_map.items():
            brightness = params["night_brightness"]
            current_brightness = get_ddc_brightness(display)
            if current_brightness != brightness:
                set_ddc_brightness(display, brightness)
                send_notification(f"Night mode: {brightness}")
                logging.info("Night mode. Brightness is set to: %d", brightness)
        return


def start_app(log_level: str = "info", log_dir: str = LOG_DIR) -> None:
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
    my_config = get_config()
    scheduler.add_job(
        brightness_control_main_function,
        replace_existing=True,
        max_instances=1,
        trigger="cron",
        hour="5-23",
        minute="*/15",
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
    start_app()
