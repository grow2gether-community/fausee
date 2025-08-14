# rdp_guard.py

import ctypes, ctypes.wintypes as wt
import logging, socket, struct, time, os, json, threading, queue
import tkinter as tk
from tkinter import simpledialog
import hmac, base64, hashlib, struct as pystruct, time as pytime

# ---------------- Logging ----------------
logging.basicConfig(
    filename='rdp_guard.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ---------------- Win32 / WTS ----------------
wtsapi32 = ctypes.WinDLL('wtsapi32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
user32   = ctypes.WinDLL('user32', use_last_error=True)

WTS_CURRENT_SERVER_HANDLE = wt.HANDLE(0)
WTS_CURRENT_SESSION = -1
WTSClientName    = 10
WTSClientAddress = 14
WTSUserName      = 5
WTSDomainName    = 7
AF_INET  = 2
AF_INET6 = 23

class WTS_CLIENT_ADDRESS(ctypes.Structure):
    _fields_ = [
        ('AddressFamily', wt.DWORD),
        ('Address', ctypes.c_ubyte * 20),
    ]

LPWSTR = wt.LPWSTR
LPVOID = wt.LPVOID
DWORD  = wt.DWORD

wtsapi32.WTSQuerySessionInformationW.argtypes = [wt.HANDLE, wt.DWORD, wt.DWORD, ctypes.POINTER(LPWSTR), ctypes.POINTER(DWORD)]
wtsapi32.WTSQuerySessionInformationW.restype = wt.BOOL
wtsapi32.WTSQuerySessionInformationA.argtypes = [wt.HANDLE, wt.DWORD, wt.DWORD, ctypes.POINTER(LPVOID), ctypes.POINTER(DWORD)]
wtsapi32.WTSQuerySessionInformationA.restype = wt.BOOL
wtsapi32.WTSFreeMemory.argtypes = [LPVOID]
wtsapi32.WTSFreeMemory.restype = None
kernel32.WTSGetActiveConsoleSessionId.restype = wt.DWORD
user32.LockWorkStation.restype  = wt.BOOL
wtsapi32.WTSLogoffSession.argtypes = [wt.HANDLE, wt.DWORD, wt.BOOL]
wtsapi32.WTSLogoffSession.restype  = wt.BOOL

# ---------------- WTS Helpers ----------------
def _wts_str(session_id: int, info_class: int) -> str:
    pp, n = LPWSTR(), DWORD(0)
    if not wtsapi32.WTSQuerySessionInformationW(WTS_CURRENT_SERVER_HANDLE, session_id, info_class, ctypes.byref(pp), ctypes.byref(n)):
        return ""
    try:
        return ctypes.wstring_at(pp) or ""
    finally:
        wtsapi32.WTSFreeMemory(pp)

def _wts_addr(session_id: int):
    pp, n = LPVOID(), DWORD(0)
    if not wtsapi32.WTSQuerySessionInformationA(WTS_CURRENT_SERVER_HANDLE, session_id, WTSClientAddress, ctypes.byref(pp), ctypes.byref(n)):
        return "", None
    try:
        addr = WTS_CLIENT_ADDRESS.from_buffer_copy(ctypes.string_at(pp, n.value))
        fam = addr.AddressFamily
        if fam == AF_INET:
            raw = bytes(addr.Address[2:6])
            return socket.inet_ntoa(raw), 'ipv4'
        elif fam == AF_INET6:
            raw = bytes(addr.Address[2:18])
            return socket.inet_ntop(socket.AF_INET6, raw), 'ipv6'
        return "", None
    finally:
        wtsapi32.WTSFreeMemory(pp)

def get_current_session_id() -> int:
    try:
        return int(os.environ.get("SESSIONNAME", "").split('#')[-1]) or kernel32.WTSGetActiveConsoleSessionId()
    except Exception:
        return kernel32.WTSGetActiveConsoleSessionId()

def is_rdp_session(session_id: int = None) -> bool:
    if session_id is None:
        session_id = WTS_CURRENT_SESSION
    if os.environ.get("SESSIONNAME","").upper().startswith("RDP"):
        return True
    if _wts_str(session_id, WTSClientName):
        return True
    ip, _ = _wts_addr(session_id)
    return bool(ip)

def get_user_identity(session_id: int = None) -> str:
    dom = _wts_str(session_id or WTS_CURRENT_SESSION, WTSDomainName)
    usr = _wts_str(session_id or WTS_CURRENT_SESSION, WTSUserName)
    return f"{dom}\\{usr}" if dom else usr

def get_rdp_client_info(session_id: int = None):
    name = _wts_str(session_id or WTS_CURRENT_SESSION, WTSClientName)
    ip, fam = _wts_addr(session_id or WTS_CURRENT_SESSION)
    return {"client_name": name or "", "client_ip": ip or "", "family": fam}

def lock_workstation():
    user32.LockWorkStation()

def logoff_session(session_id: int = None):
    wtsapi32.WTSLogoffSession(WTS_CURRENT_SERVER_HANDLE, session_id or WTS_CURRENT_SESSION, True)

# ---------------- VPN Check ----------------
VPN_CIDRS = [("10.8.0.0", 16), ("192.168.0.0", 16)]

def ip_in_cidrs(ip: str, cidrs=VPN_CIDRS) -> bool:
    if not ip: return False
    try:
        x = struct.unpack("!I", socket.inet_aton(ip))[0]
        for net, pfx in cidrs:
            n = struct.unpack("!I", socket.inet_aton(net))[0]
            mask = (0xFFFFFFFF << (32 - pfx)) & 0xFFFFFFFF
            if (x & mask) == (n & mask):
                return True
    except Exception:
        return False
    return False

# ---------------- TOTP ----------------
def _hotp(secret_bytes: bytes, counter: int, digits: int=6) -> str:
    msg = pystruct.pack(">Q", counter)
    h = hmac.new(secret_bytes, msg, hashlib.sha1).digest()
    o = h[19] & 0x0F
    code = (pystruct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % (10 ** digits)
    return str(code).zfill(digits)

def totp_now(secret_b32: str, step: int=30, digits: int=6) -> str:
    key = base64.b32decode(secret_b32.replace(" ", "").upper())
    counter = int(pytime.time() // step)
    return _hotp(key, counter, digits)

def totp_verify(secret_b32: str, code: str, window: int=1, step: int=30) -> bool:
    code = code.strip()
    for skew in range(-window, window+1):
        if totp_now(secret_b32, step=step) == code:
            return True
    return False

# ---------------- GUI Prompt ----------------
def prompt_totp(timeout_sec=30):
    q = queue.Queue()
    def ui():
        root = tk.Tk()
        root.withdraw()
        try:
            code = simpledialog.askstring("Step-up verification", "Enter 6-digit code", show='*')
            q.put(code or "")
        except Exception:
            q.put("")
        finally:
            try: root.destroy()
            except: pass
    t = threading.Thread(target=ui, daemon=True)
    t.start()
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            return q.get_nowait()
        except queue.Empty:
            time.sleep(0.1)
    return ""

# ---------------- Config ----------------
SECRETS_FILE = "rdp_totp_secrets.json"
MAX_ATTEMPTS = 3

def load_user_secret(identity: str) -> str:
    try:
        with open(SECRETS_FILE, "r") as f:
            data = json.load(f)
        return data.get(identity, "")
    except Exception:
        return ""

# ---------------- Main Enforcement ----------------
def enforce_rdp_controls():
    sess_id = get_current_session_id()
    identity = get_user_identity(sess_id) or "UNKNOWN"

    # Detect session type
    if not is_rdp_session(sess_id):
        logging.info(f"Session type: LOCAL — user {identity} is logged in locally (no RDP).")
        return {"mode": "local", "user": identity, "allowed": True}

    # If RDP
    client = get_rdp_client_info(sess_id)
    cip = client["client_ip"]
    logging.info(f"Session type: RDP — user {identity} connected from {client}")

    # VPN check
    if not ip_in_cidrs(cip):
        logging.warning(f"RDP denied for {identity}: client {cip} not in allowed VPN ranges.")
        lock_workstation()
        return {"mode": "rdp", "user": identity, "allowed": False, "reason": "not on VPN"}

    # TOTP check
    secret = load_user_secret(identity)
    if not secret:
        logging.warning(f"RDP denied for {identity}: no TOTP secret found.")
        lock_workstation()
        return {"mode": "rdp", "user": identity, "allowed": False, "reason": "no TOTP"}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        code = prompt_totp()
        if totp_verify(secret, code):
            logging.info(f"RDP step-up authentication SUCCESS for {identity} on attempt {attempt}.")
            return {"mode": "rdp", "user": identity, "allowed": True}
        logging.warning(f"RDP step-up authentication FAILED for {identity} on attempt {attempt}.")

    logging.error(f"RDP access denied for {identity}: TOTP failed after {MAX_ATTEMPTS} attempts.")
    lock_workstation()
    return {"mode": "rdp", "user": identity, "allowed": False, "reason": "TOTP failed"}
