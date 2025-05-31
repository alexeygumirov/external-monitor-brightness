#!/bin/bash
# This script installs the external-monitor-brightness application in the user's home directory
# and generates a symbolic link to the application executable in the user's home directory.

MAX_VERSION=3140
MIN_VERSION=3110
PYTHON=""
VENV_DEFAULT_PATH="${HOME}/.local/virtualenv/external-monitor-brightness"
CONFIG_DIR="${HOME}/.config/external-monitor-brightness"
APP_NAME="external-monitor-brightness"

check_python_version() {
    if command -v python3 &> /dev/null; then
        version=$(python3 --version | awk '{print $2}' | sed 's/\.//g')
        if test $version -lt $MAX_VERSION && test $version -ge $MIN_VERSION; then
            PYTHON=python3
        else
            echo "Please install Python 3.11, 3.12, 3.13 and try again"
            exit 1
        fi
    fi
}

check_ddcutil_presence() {
    if ! command -v ddcutil &> /dev/null; then
        echo "Warning! This application requires `ddcutil` to be installed."
        read -p "Do you want to continue? (y/n): " choice
        case "$choice" in
            y|Y ) echo "Continuing installation...";;
            n|N ) echo "Installation aborted."; exit 1;;
            * ) echo "Invalid choice. Installation aborted."; exit 1;;
        esac
    fi
}

# Create parsing of input parameters/switches for this script. If no -p switch is provided, the default virtual environment path is used.
while getopts ":p:" opt; do
    case $opt in
        p)
            VENV_PATH=$OPTARG
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            exit 1
            ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2
            exit 1
            ;;
    esac
done

if [ -z "$VENV_PATH" ]; then
    VENV_PATH=$VENV_DEFAULT_PATH
fi

echo "Checking if ddcutil is installed"
check_ddcutil_presence

echo "Checking if Python is installed"
check_python_version

# nosemgrep: unquoted-variable-expansion-in-command
echo
echo "Cleaning old virtual environment"
if test -d "${VENV_PATH}"; then
    rm -rf "${VENV_PATH}"
fi

echo "Creating a virtual environment for application in the ${VENV_PATH}"
if [ ! -d "${VENV_PATH}" ]; then
    mkdir -p "${VENV_PATH}"
    if "$PYTHON" -m venv "${VENV_PATH}" --prompt "external-monitor-brightness"; then
        echo "Virtual environment is created"
    else
        echo "Failed to create virtual environment"
        exit 1
    fi
else
    echo "Updating the virtual environment"
    if "$PYTHON" -m venv "${VENV_PATH}" --prompt "external-monitor-brightness" --update --update-deps; then
        echo "Virtual environment is updated"
    else
        echo "Failed to update virtual environment"
        exit 1
    fi
fi

echo
echo "Activating the virtual environment"
source "${VENV_PATH}"/bin/activate
command -v "$PYTHON"

echo
echo "Installing external-monitor-brightness application"
pip3 install .

# Check the OS and create a symbolic link to the external-monitor-brightness executable
echo
if [ "$(uname -s)" = "Linux" ]; then
    echo "Creating symbolic link to external-monitor-brightness application in ~/.local/bin"
    echo
    ln -s -f "${VENV_PATH}"/bin/"${APP_NAME}" ~/.local/bin/.
else
    echo "Unsupported OS"
    exit
fi

# creating default configuration file
if [ "$(uname -s)" = "Linux" ]; then
    echo "Creating default configuration directory:"
    echo "  ${CONFIG_DIR}"
    echo
    if [ ! -d "${CONFIG_DIR}" ]; then
        mkdir -p "${CONFIG_DIR}"
        cp config/config.json "${CONFIG_DIR}"/.
    else
        echo "Configuration directory already exists"
    fi
else
    echo "Unsupported OS"
    exit
fi
