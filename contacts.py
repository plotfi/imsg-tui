
import argparse, curses, json, re, subprocess, threading, time

def normalize_phone(s):
    s = s.strip()
    if s.startswith("+"):
        return "+" + re.sub(r"\D", "", s[1:])
    return re.sub(r"\D", "", s)

def parse_vcf(path):
    contacts = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return contacts
    for entry in re.split(r"(?i)END:VCARD", text):
        fn_m = re.search(r"(?i)^FN[;:](.+)$", entry, re.MULTILINE)
        if not fn_m:
            continue
        name = fn_m.group(1).strip()
        for tel_m in re.finditer(r"(?i)^TEL[;:](.+)$", entry, re.MULTILINE):
            val = tel_m.group(1).strip()
            # strip any TYPE= params before the actual number (e.g. "type=CELL:+1234567890")
            if ":" in val:
                val = val.rsplit(":", 1)[-1].strip()
            norm = normalize_phone(val)
            if norm:
                contacts[norm] = name
        for em_m in re.finditer(r"(?i)^EMAIL[;:](.+)$", entry, re.MULTILINE):
            val = em_m.group(1).strip()
            if ":" in val:
                val = val.rsplit(":", 1)[-1].strip()
            contacts[val.lower()] = name
    return contacts

def resolve_name(contacts, identifier):
    if not contacts or not identifier:
        return None
    # try direct lookup (email)
    if identifier.lower() in contacts:
        return contacts[identifier.lower()]
    # try normalized phone lookup
    norm = normalize_phone(identifier)
    if norm in contacts:
        return contacts[norm]
    return None
