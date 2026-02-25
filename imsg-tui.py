#!/usr/bin/env python3

"""iMessage TUI client using imsg CLI (https://github.com/steipete/imsg).
Usage: python imsg_client.py [--imsg-path /path/to/imsg]
"""

from __future__ import annotations
import argparse, curses, json, subprocess, threading, time
from datetime import datetime

from contacts import normalize_phone, parse_vcf, resolve_name

SIDEBAR_W = 28
POLL_SEC = 1

LOAD_HISTORY_LIMIT= "10"
POLL_LIMIT= "2"
CHAT_ROSTER_LIMIT= "7"

DEBUG = False

load_history_dbg = ""
poll_loop_dbg = ""

if DEBUG:
    load_history_dbg = " <<< LOAD"
    poll_loop_dbg = " <<< POLL"

def imsg(bin, *args):
    try:
        r = subprocess.run([bin]+list(args), capture_output=True, text=True, timeout=15)
        return [json.loads(l) for l in r.stdout.strip().splitlines() if l.strip()] if r.returncode == 0 else []
    except Exception:
        return []

def main(stdscr, bin, contacts=None):
    contacts = contacts or {}
    curses.curs_set(1); curses.use_default_colors()
    for i, c in enumerate([curses.COLOR_CYAN, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED], 1):
        curses.init_pair(i, c, -1)

    chats = []      # [{id, name, identifier, service, msgs:[], rowid:0, unread:0}]
    sel, active, buf = 0, -1, ""
    lock = threading.Lock()
    running = [True]

    def load_chats():
        nonlocal chats
        raw = imsg(bin, "chats", "--limit", CHAT_ROSTER_LIMIT, "--json")
        with lock:
            chats = [{"id": c.get("id"),
                       "name": resolve_name(contacts, c.get("identifier","")) or c.get("name") or c.get("identifier","?"),
                       "identifier": c.get("identifier",""), "service": c.get("service",""),
                       "msgs": [], "rowid": 0, "unread": 0} for c in raw]

    def load_history(chat):
        raw = imsg(bin, "history", "--chat-id", str(chat["id"]), "--limit", LOAD_HISTORY_LIMIT, "--json")
        msgs, mr = [], chat["rowid"]
        for m in raw:
            rid = m.get("id", 0)
            if rid > mr: mr = rid
            txt = m.get("text", "")
            if not txt: continue
            try: ts = datetime.fromisoformat(m["created_at"].replace("Z","+00:00")).strftime("%H:%M")
            except Exception: ts = "??:??"
            sender = m.get("sender") or chat["name"]
            who = "me" if m.get("is_from_me") else (resolve_name(contacts, sender) or sender)
            msgs.append((ts, who, txt + load_history_dbg))
        msgs.reverse()
        with lock:
            chat["msgs"] = msgs; chat["rowid"] = mr

    def poll_loop():
        while running[0]:
            time.sleep(POLL_SEC)
            with lock:
                snapshot = [(i, c) for i, c in enumerate(chats)]
            for i, c in snapshot:
                if not running[0]: break
                raw = imsg(bin, "history", "--chat-id", str(c["id"]), "--limit", POLL_LIMIT, "--json")
                new, mr = [], c["rowid"]
                for m in raw:
                    rid = m.get("id", 0)
                    if rid <= c["rowid"]: continue
                    if rid > mr: mr = rid
                    txt = m.get("text", "")
                    if not txt: continue
                    try: ts = datetime.fromisoformat(m["created_at"].replace("Z","+00:00")).strftime("%H:%M")
                    except Exception: ts = "??:??"
                    sender = m.get("sender") or c["name"]
                    who = "me" if m.get("is_from_me") else (resolve_name(contacts, sender) or sender)
                    new.append((ts, who, txt + poll_loop_dbg))
                if new:
                    with lock:
                        c["msgs"].extend(new); c["rowid"] = mr
                        if i != active: c["unread"] += len(new)
                    draw()

    def mkwins():
        h, w = stdscr.getmaxyx(); sw = min(SIDEBAR_W, w//3)
        return {"st": curses.newwin(1,w,0,0), "ro": curses.newwin(h-3,sw,1,0),
                "dv": curses.newwin(h-3,1,1,sw), "ch": curses.newwin(h-3,max(1,w-sw-1),1,sw+1),
                "sp": curses.newwin(1,w,h-2,0), "in": curses.newwin(1,w,h-1,0)}, h, w, sw

    wins, H, W, SW = mkwins()

    def draw():
        try:
            with lock:
                h, w = H, W
                ac = chats[active] if 0 <= active < len(chats) else None

                # Status bar
                wn = wins["st"]; wn.erase(); wn.bkgd(' ', curses.A_REVERSE)
                st = f" {ac['service']} | {ac['name']}" if ac else f" iMessage | {len(chats)} chats | Up/Down Tab Esc Ctrl+C"
                wn.addnstr(0,0,st,w-1,curses.A_REVERSE|curses.A_BOLD); wn.refresh()

                # Roster
                wn = wins["ro"]; wn.erase(); rh, rw = wn.getmaxyx()
                try:
                    wn.addnstr(0,0," CHATS",rw-1,curses.A_BOLD|curses.color_pair(3))
                    wn.addnstr(1,0," "+"-"*(rw-2),rw-1,curses.color_pair(3))
                except curses.error: pass
                for i, c in enumerate(chats):
                    if i+2 >= rh-1: break
                    badge = f" ({c['unread']})" if c["unread"] else ""
                    arrow = " <" if i == active else ""
                    ln = f" {c['name'][:rw-5-len(badge)-len(arrow)]}{badge}{arrow}".ljust(rw-1)[:rw-1]
                    attr = curses.A_REVERSE if i == sel else (curses.color_pair(2)|curses.A_BOLD if c["unread"] else curses.color_pair(1))
                    try: wn.addnstr(i+2,0,ln,rw-1,attr)
                    except curses.error: pass
                wn.refresh()

                # Divider
                wn = wins["dv"]; wn.erase()
                for i in range(wn.getmaxyx()[0]):
                    try: wn.addch(i,0,"|",curses.color_pair(3))
                    except curses.error: pass
                wn.refresh()

                # Chat area
                wn = wins["ch"]; wn.erase(); ch, cw = wn.getmaxyx()
                if not ac:
                    try: wn.addnstr(ch//2,max(0,(cw-18)//2),"Tab to open a chat",cw-1,curses.color_pair(3))
                    except curses.error: pass
                else:
                    for i, (ts, who, txt) in enumerate(ac["msgs"][-(ch):]):
                        if i >= ch-1: break
                        try:
                            col = curses.color_pair(1) if who == "me" else curses.color_pair(2)
                            wn.addnstr(i,1,f"{ts} ",6,curses.color_pair(3))
                            wn.addnstr(f"{who}: ",len(who)+2,col|curses.A_BOLD)
                            rem = cw-8-len(who)-2
                            if rem > 0: wn.addnstr(txt,rem)
                        except curses.error: pass
                wn.refresh()

                # Separator + input
                wn = wins["sp"]; wn.erase()
                try: wn.addnstr(0,0,"-"*(w-1),w-1,curses.color_pair(3))
                except curses.error: pass
                wn.refresh()

                wn = wins["in"]; wn.erase(); pr = " iMessage> " if ac else " > "
                try: wn.addnstr(0,0,pr,len(pr),curses.color_pair(1)|curses.A_BOLD); wn.addstr(buf[:w-len(pr)-1])
                except curses.error: pass
                wn.refresh()
        except Exception: pass

    # Init
    load_chats(); draw()
    threading.Thread(target=poll_loop, daemon=True).start()

    while running[0]:
        try: ch = stdscr.getch()
        except KeyboardInterrupt: break

        with lock:
            if ch == curses.KEY_RESIZE:
                wins, H, W, SW = mkwins()
            elif ch == curses.KEY_UP and chats:
                sel = max(0, sel-1)
            elif ch == curses.KEY_DOWN and chats:
                sel = min(len(chats)-1, sel+1)
            elif ch == 9 and chats:  # Tab
                active = sel
                if 0 <= active < len(chats):
                    chats[active]["unread"] = 0
                    c = chats[active]
                    threading.Thread(target=lambda: (load_history(c), draw()), daemon=True).start()
            elif ch == 27:  # Esc
                active = -1
            elif ch in (10, 13) and buf.strip():
                txt = buf.strip(); buf = ""
                if txt == "/quit": break
                elif txt == "/refresh":
                    threading.Thread(target=lambda: (load_chats(), draw()), daemon=True).start()
                elif 0 <= active < len(chats):
                    c = chats[active]; handle = c["identifier"]
                    if handle:
                        # c["msgs"].append((datetime.now().strftime("%H:%M"), "me", txt + "foo"))
                        threading.Thread(target=lambda t=txt,h=handle: imsg(bin,"send","--to",h,"--text",t), daemon=True).start()
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                buf = buf[:-1]
            elif ch == 21: buf = ""  # Ctrl+U
            elif 32 <= ch <= 126: buf += chr(ch)
            else: continue
        draw()

    running[0] = False

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="iMessage TUI")
    p.add_argument("--imsg-path", default="imsg", help="Path to imsg binary")
    p.add_argument("--vcf", default=None, help="Path to vCard (.vcf) file for contact name resolution")
    args = p.parse_args()
    vcf_contacts = parse_vcf(args.vcf) if args.vcf else {}
    curses.wrapper(main, args.imsg_path, vcf_contacts)
