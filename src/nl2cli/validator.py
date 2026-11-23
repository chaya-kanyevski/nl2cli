"""בדיקות פלט: פורמט ותקינות תחבירית (היוריסטית, ללא הרצה)."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from .shell_utils import first_token, split_segments

KNOWN_COMMANDS = {
    "windows-cmd": set("""
        dir cd chdir cls copy xcopy robocopy move ren rename del erase rd rmdir md mkdir type more
        find findstr sort echo set setx ver vol hostname whoami ipconfig ping tracert nslookup netstat
        arp route netsh tasklist taskkill systeminfo wmic sc net shutdown format chkdsk diskpart attrib
        icacls takeown tree fc comp where date time title color start exit powershell pwsh cmd clip
        certutil schtasks reg fsutil getmac driverquery path pushd popd mklink assoc ftype cipher curl
        tar winget choco git python py pip npm node code notepad explorer bcdedit vssadmin for if
        timeout mode pathping query qwinsta logoff runas call rem openfiles
    """.split()),
    "linux-bash": set("""
        ls cd pwd cat less more head tail grep egrep fgrep find locate wc sort uniq cut awk sed tr echo
        printf env printenv export uname hostname whoami id date cal uptime ps top htop kill pkill
        killall df du free lsblk mount umount ip ifconfig ss netstat ping traceroute curl wget nslookup
        dig host mkdir rmdir rm cp mv touch ln chmod chown chgrp tar gzip gunzip zip unzip file stat
        tree which whereis xargs tee diff history clear sudo apt apt-get yum dnf systemctl service
        journalctl shutdown reboot poweroff halt mkfs dd lsof crontab ssh scp rsync git python python3
        pip pip3 npm node nano vim vi basename dirname realpath readlink sleep timeout nproc lscpu
        vmstat watch hostnamectl lsb_release nl true false test seq bash sh time nice jq base64
        md5sum sha256sum column fold rev tac shuf type command alias source exit for while if
        snap ufw iptables useradd userdel passwd who w last groups arch getconf
    """.split()),
}


@dataclass
class SyntaxResult:
    ok: bool
    note: str = ""


def _balanced_quotes(command: str, os_key: str) -> bool:
    if command.count('"') % 2:
        return False
    if os_key == "linux-bash":
        # ספירה פשוטה של ' מחוץ ל-" (מספיקה למקרים הנפוצים)
        outside, in_dq = 0, False
        for ch in command:
            if ch == '"':
                in_dq = not in_dq
            elif ch == "'" and not in_dq:
                outside += 1
        return outside % 2 == 0
    return True


def check_syntax(command: str, os_key: str) -> SyntaxResult:
    if not command.strip():
        return SyntaxResult(False, "פקודה ריקה")
    if "\n" in command.strip():
        return SyntaxResult(False, "יותר משורה אחת")
    if not _balanced_quotes(command, os_key):
        return SyntaxResult(False, "מרכאות לא מאוזנות")

    if os_key == "linux-bash" and shutil.which("bash"):
        # bash -n מנתח תחביר בלבד ואינו מריץ דבר
        proc = subprocess.run(["bash", "-n", "-c", command], capture_output=True,
                              text=True, timeout=5)
        if proc.returncode != 0:
            return SyntaxResult(False, f"bash -n: {proc.stderr.strip()[:200]}")

    unknown = [first_token(s, os_key) for s in split_segments(command, os_key)]
    unknown = [t for t in unknown if t and t not in KNOWN_COMMANDS[os_key]
               and not t.endswith((".bat", ".cmd", ".ps1", ".sh", ".py"))]
    if unknown:
        return SyntaxResult(False, f"פקודה לא מוכרת ל-{os_key}: {', '.join(unknown)}")
    return SyntaxResult(True, "")
