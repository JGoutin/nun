"""Configuration"""
import os

# Application name
APP_NAME = __name__.split(".")[0]

# Directories
if os.name == "nt":
    CONFIG_DIR = os.path.join(os.path.expandvars("%APPDATA%"), APP_NAME)
    DATA_DIR = os.path.join(os.path.expandvars("%LOCALAPPDATA%"), APP_NAME)
    CACHE_DIR = os.path.join(DATA_DIR, "cache")

elif os.getuid() != 0:
    CONFIG_DIR = os.path.join(
        os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), APP_NAME
    )
    DATA_DIR = os.path.join(
        os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), APP_NAME
    )
    CACHE_DIR = os.path.join(
        os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), APP_NAME
    )

else:
    CONFIG_DIR = f"/etc/{APP_NAME}"
    DATA_DIR = f"/var/lib/{APP_NAME}"
    CACHE_DIR = f"/var/cache/{APP_NAME}"

# Ensure directories exists and have proper access rights
for _path in (CONFIG_DIR, DATA_DIR, CACHE_DIR):
    os.makedirs(_path, exist_ok=True)
    os.chmod(_path, 0o700)
del _path
