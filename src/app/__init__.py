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

__VERSION__ = "1.3.0"


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

    arguments = parser.parse_args()

    if len(sys.argv) == 1:
        start_app(log_dir=arguments.log_directory)

    if len(sys.argv) > 1:
        if arguments.verbose:
            start_app(log_level="debug", log_dir=arguments.log_directory)
        else:
            start_app(log_dir=arguments.log_directory)
