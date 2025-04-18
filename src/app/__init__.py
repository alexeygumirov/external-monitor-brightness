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

import argparse
import sys
from app.application import start_app

__VERSION__ = "2.3.3"


def main():
    parser = argparse.ArgumentParser(
        description="Utility to change brightness of external monitors on Linux."
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__VERSION__}"
    )
    parser.add_argument(
        "-vv", "--verbose", action="store_true", help="Enable verbose mode"
    )
    parser.add_argument(
        "-l",
        "--log-directory",
        type=str,
        help="Directory to store logs",
        default="/tmp/external-monitor-brightness",
    )
    parser.add_argument(
        "-s",
        "--adjust-steps",
        type=int,
        help="Number of steps to adjust brightness. (default: 5)",
        default=None,
    )
    parser.add_argument(
        "-i",
        "--cron-interval",
        type=int,
        help="Time interval in minutes to check for brightness adjustment. (default: 15)",
        default=None,  # can be only 10, 12, 15, 20 and 30
    )
    parser.add_argument(
        "-o",
        "--sunrise-sunset-offset",
        type=int,
        help="The offset in minutes to adjust the time of sunrise and sunset (minutes). (default: 60)",
        default=None,
    )

    arguments = parser.parse_args()
    if arguments.adjust_steps and arguments.adjust_steps not in range(1, 11):
        print("Number of steps must be in the range of 1 - 10")
        sys.exit(1)
    if arguments.cron_interval and arguments.cron_interval not in [10, 12, 15, 20, 30]:
        print("Cron interval can be 10, 12, 15, 20 or 30 min")
        sys.exit(1)
    if arguments.sunrise_sunset_offset and (
        arguments.sunrise_sunset_offset < 0 or arguments.sunrise_sunset_offset > 120
    ):
        print("Sunrise and sunset offset must be in the range of 0 - 120")
        sys.exit(1)

    if arguments.verbose:
        start_app(
            adjust_steps=arguments.adjust_steps,
            cron_interval=arguments.cron_interval,
            sunrise_sunset_offset=arguments.sunrise_sunset_offset,
            log_level="debug",
            log_dir=arguments.log_directory,
        )
    else:
        start_app(
            adjust_steps=arguments.adjust_steps,
            cron_interval=arguments.cron_interval,
            sunrise_sunset_offset=arguments.sunrise_sunset_offset,
            log_dir=arguments.log_directory,
        )
