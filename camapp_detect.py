# import psutil
# import time

# def is_camera_app_running():
#     """
#     Checks if the native Windows 'Camera' app is currently running.

#     The process name for the UWP (Universal Windows Platform) Camera app
#     is 'WindowsCamera.exe'. This function iterates through all running
#     processes and returns True if a process with this name is found.

#     Returns:
#         bool: True if the Camera app is running, False otherwise.
#     """
#     for process in psutil.process_iter(['name']):
#         try:
#             # The name() method gets the process name.
#             if process.info['name'].lower() == 'windowscamera.exe':
#                 # Found the process
#                 return True
#         except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
#             # These exceptions can occur if a process terminates
#             # while we are iterating, or if we don't have permission to access it.
#             # We can safely ignore them.
#             pass
#     # If the loop completes without finding the process
#     return False

# if __name__ == "__main__":
#     print("Starting camera app detection...")
#     print("Open the Windows 'Camera' app to see the status change.")
#     print("Press Ctrl+C to stop the script.")

#     try:
#         while True:
#             if is_camera_app_running():
#                 # The \r character moves the cursor to the beginning of the line,
#                 # and end='' prevents a newline. This creates an updating effect.
#                 print("\r✅ Status: Windows Camera app is RUNNING.", end='')
#             else:
#                 print("\r❌ Status: Windows Camera app is NOT running.", end='')
            
#             # Wait for a second before checking again to avoid high CPU usage.
#             time.sleep(1)
            
#     except KeyboardInterrupt:
#         print("\nScript stopped by user.")

import psutil
import time
import os
import ctypes

def is_admin():
    """Check if the script is running with administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def force_close_camera_app():
    """
    Finds and forcefully terminates the native Windows 'Camera' app process.

    Returns:
        bool: True if the process was found and an attempt to kill it was made,
              False otherwise.
    """
    process_found = False
    # The process name for the UWP Camera app is 'WindowsCamera.exe'
    camera_process_name = "windowscamera.exe"

    # Iterate through all running processes
    for process in psutil.process_iter(['pid', 'name']):
        try:
            if process.info['name'].lower() == camera_process_name:
                print(f"Found {camera_process_name} (PID: {process.info['pid']}). Terminating...")
                # Get the process object by its PID and terminate it
                p = psutil.Process(process.info['pid'])
                p.kill() # Use kill() for forceful termination
                print(f"Process {camera_process_name} terminated.")
                process_found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # AccessDenied can happen if the script doesn't have enough permissions
            print(f"Access Denied: Could not terminate {camera_process_name}.")
            print("Please try running the script as an administrator.")
            # We still found it, so return True
            return True
        except psutil.ZombieProcess:
            # Zombie processes are already dead, so we can ignore them
            pass
            
    return process_found

if __name__ == "__main__":
    if not is_admin():
        print("Warning: Script is not running as an administrator.")
        print("It may not be able to close the Camera app.")
        print("-" * 30)

    print("Starting Camera App monitor...")
    print("This script will automatically close the Windows Camera app if it opens.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            force_close_camera_app()
            # Wait for a short period to avoid high CPU usage
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")