"""Application self-update functionality."""

import os
import sys
import json
import time
import ssl
import shutil
import subprocess
import urllib.request
import urllib.error

# GitHub repository coordinates
REPO_OWNER = "ts-haibv"
REPO_NAME = "FlashTool"


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a semantic version string (e.g., '1.2.4', 'v1.3.0-beta') into an integer tuple."""
    cleaned = version_str.lower().strip().lstrip("v")
    parts = []
    for part in cleaned.split("."):
        digits = []
        for char in part:
            if char.isdigit():
                digits.append(char)
            else:
                break
        parts.append(int("".join(digits)) if digits else 0)
    return tuple(parts)


def check_for_updates(current_version: str) -> dict:
    """Check GitHub Releases for a newer version.

    Returns:
        dict: Release metadata indicating if an update is available.

    Raises:
        Exception: If the API request or response parsing fails.
    """
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "FlashTool-Updater"})

    # Try default context first, fallback to unverified context if SSL fails
    try:
        context = ssl.create_default_context()
        response = urllib.request.urlopen(req, context=context, timeout=8)
    except Exception as ssl_err:
        print(f"Default SSL connection failed: {ssl_err}. Retrying with unverified context...", file=sys.stderr)
        try:
            context = ssl._create_unverified_context()
            response = urllib.request.urlopen(req, context=context, timeout=8)
        except Exception as fallback_err:
            print(f"Fallback SSL connection failed: {fallback_err}", file=sys.stderr)
            raise fallback_err

    try:
        with response as res:
            if res.status == 200:
                data = json.loads(res.read().decode("utf-8"))
                tag_name = data.get("tag_name", "")
                if not tag_name:
                    raise ValueError("Tag name missing from GitHub API response")

                latest_ver = parse_version(tag_name)
                curr_ver = parse_version(current_version)

                if latest_ver > curr_ver:
                    assets = data.get("assets", [])
                    download_url = None
                    asset_name = None
                    size = 0

                    # Match asset name to current platform
                    is_windows = sys.platform == "win32"
                    target_asset = "FlashTool-Windows.exe" if is_windows else "FlashTool-Linux"

                    for asset in assets:
                        if asset.get("name") == target_asset:
                            download_url = asset.get("browser_download_url")
                            asset_name = asset.get("name")
                            size = asset.get("size", 0)
                            break

                    return {
                        "update_available": True,
                        "latest_version": tag_name,
                        "release_notes": data.get("body", "No release notes provided."),
                        "download_url": download_url,
                        "asset_name": asset_name,
                        "size": size,
                        "html_url": data.get("html_url", ""),
                    }
                else:
                    return {
                        "update_available": False,
                        "latest_version": tag_name,
                    }
            else:
                raise urllib.error.HTTPError(
                    url, res.status, "HTTP Error", res.headers, None
                )
    except Exception as e:
        print(f"Error parsing update response: {e}", file=sys.stderr)
        raise e


def download_file_with_progress(
    url: str,
    dest_path: str,
    progress_callback,
    check_stopped_callback,
) -> bool:
    """Download a file chunk-by-chunk with progress reporting and cancellation capability.

    Args:
        url: URL of the file.
        dest_path: Absolute path where file is saved.
        progress_callback: Callable taking (downloaded_bytes, total_bytes, elapsed_seconds).
        check_stopped_callback: Callable returning True if the download should be cancelled.

    Returns:
        bool: True if download completed successfully, False otherwise.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "FlashTool-Updater"})
    context = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, context=context, timeout=12) as response:
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            start_time = time.time()

            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)

            with open(dest_path, "wb") as f:
                while True:
                    if check_stopped_callback():
                        return False

                    chunk = response.read(16384)  # 16 KB chunks
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    elapsed = time.time() - start_time
                    progress_callback(downloaded, total_size, elapsed)

            return True
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
        return False


def apply_update(new_file_path: str) -> bool:
    """Replace the currently running executable with the newly downloaded update.

    Args:
        new_file_path: Absolute path to the newly downloaded binary.

    Returns:
        bool: True if replacement was successful, False otherwise.
    """
    if not getattr(sys, "frozen", False):
        return False

    current_exe = sys.executable
    backup_exe = current_exe + ".bak"

    # Check if we have write access to the executable and its directory
    has_write_access = os.access(current_exe, os.W_OK) and os.access(
        os.path.dirname(current_exe), os.W_OK
    )

    if not has_write_access and sys.platform != "win32":
        # Attempt pkexec elevation for system-installed Linux packages
        pkexec_path = shutil.which("pkexec")
        if pkexec_path:
            try:
                # Use pkexec to copy the temp file over the target and set permissions
                # Since the current process doesn't have write access, elevated 'mv' is needed.
                cmd = [
                    pkexec_path,
                    "sh",
                    "-c",
                    f"mv '{new_file_path}' '{current_exe}' && chmod 755 '{current_exe}'",
                ]
                res = subprocess.run(cmd, check=False)
                if res.returncode == 0:
                    return True
            except Exception as pe:
                print(f"Elevation via pkexec failed: {pe}", file=sys.stderr)

    try:
        # 1. Clean up old backup if it exists from previous attempts
        if os.path.exists(backup_exe):
            try:
                os.remove(backup_exe)
            except Exception:
                pass

        # 2. Rename the currently running executable to .bak
        os.rename(current_exe, backup_exe)

        # 3. Move/Rename the new file to the official executable path
        shutil.move(new_file_path, current_exe)

        # 4. Make executable on Linux/macOS
        if sys.platform != "win32":
            os.chmod(current_exe, 0o755)
            # On Linux/Unix, we can delete the running backup file immediately
            try:
                os.remove(backup_exe)
            except Exception:
                pass

        return True
    except PermissionError as pe:
        print(f"Permission error applying update: {pe}", file=sys.stderr)
        raise PermissionError(
            "Permission denied: The application is installed at system level (e.g. /usr/bin) "
            "and requires root/administrative privileges to modify.\n\n"
            "Please run the updater as root or manually download and install the latest package."
        ) from pe
    except Exception as e:
        print(f"Error applying update: {e}", file=sys.stderr)
        # Attempt recovery by restoring backup if original file disappeared
        if os.path.exists(backup_exe) and not os.path.exists(current_exe):
            try:
                os.rename(backup_exe, current_exe)
            except Exception:
                pass
        raise e


def cleanup_old_updates():
    """Remove .bak files left behind from updates on previous runs (specifically Windows)."""
    if not getattr(sys, "frozen", False):
        return

    current_exe = sys.executable
    for ext in (".bak", ".old"):
        bak_path = current_exe + ext
        if os.path.isfile(bak_path):
            try:
                os.remove(bak_path)
            except Exception as e:
                print(f"Failed to remove backup {bak_path}: {e}", file=sys.stderr)


def restart_application():
    """Restart the application immediately."""
    current_exe = sys.executable
    args = sys.argv[1:]

    # Clean up environment variables (especially important for PyInstaller on Linux)
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        if "LD_LIBRARY_PATH_ORIG" in env:
            env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
            del env["LD_LIBRARY_PATH_ORIG"]
        elif "LD_LIBRARY_PATH" in env:
            del env["LD_LIBRARY_PATH"]

        if "_MEIPASS" in env:
            del env["_MEIPASS"]

    try:
        # Spawn the new process in a detached session so it lives independently
        if sys.platform == "win32":
            subprocess.Popen([current_exe] + args, env=env)
        else:
            subprocess.run(["sync"], check=False)  # Ensure filesystem syncs
            subprocess.Popen([current_exe] + args, env=env, start_new_session=True)
        sys.exit(0)
    except Exception as e:
        print(f"Failed to restart application: {e}", file=sys.stderr)
        sys.exit(1)
