import psutil
import win32gui
import win32process


def select_endless_pid():
    """Find all processes named 'endless.exe' and let user pick one if there's more than one."""
    endless_pids = []
    for proc in psutil.process_iter():
        if proc.name().lower() == 'endless.exe':
            endless_pids.append(proc.pid)

    if not endless_pids:
        print("No 'endless.exe' process found.")
        return None

    if len(endless_pids) == 1:
        pid = endless_pids[0]
        print(f"Found one 'endless.exe' process (PID {pid}).")
        return pid

    print("Multiple 'endless.exe' processes found:")
    for i, pid in enumerate(endless_pids, start=1):
        print(f"{i}. PID = {pid}")

    while True:
        choice = input("Select the process # to attach: ").strip()
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(endless_pids):
                return endless_pids[index - 1]
        print("Invalid selection. Try again.")


def focus_endless_window(pid):
    def callback(hwnd, list_to_append):
        list_to_append.append((hwnd, win32gui.GetWindowText(hwnd)))

    window_list = []
    win32gui.EnumWindows(callback, window_list)
    for i in window_list:
        w = i[0]
        p = win32process.GetWindowThreadProcessId(w)[1]
        if pid == p:
            win32gui.ShowWindow(w, 5)
            win32gui.SetForegroundWindow(w)
            win32gui.SetActiveWindow(w)
            break
