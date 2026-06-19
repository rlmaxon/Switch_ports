# Switch Ports — NetOps Switch Manager

A Streamlit UI for browsing and managing IT network switch port/VLAN data across
a simulated 220-switch fleet (Cisco + Arista), including stacked switches,
modular chassis switches, and a spine/leaf data center fabric.

## Files

- `app.py` — Streamlit application
- `switches.json` — 220 switch records (hostname, mgmt IP, site, role, chassis type, etc.)
- `ports.json` — ~19,600 port records (admin/oper status, VLAN mode, MAC count, etc.)
- `vlans.json` — VLAN registry (20 VLANs)
- `requirements.txt` — Python dependencies

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data model notes

- **switches.json**: one row per switch. `chassis_type` is `fixed`, `stack`, or `modular`.
  Stacked switches have `stack_members` set; modular chassis switches have line-card slots
  baked into port names. `fabric` is `campus` or `spine-leaf`.
- **ports.json**: one row per physical port, linked to switches.json via `hostname`.
  Includes admin_status, oper_status, mode (access/trunk), VLAN info, speed/duplex,
  mac_count, and last_changed timestamp.
- **vlans.json**: VLAN ID → name registry.
- The CHI site includes a dedicated spine/leaf data center fabric (4 spines, 16 leaves)
  in a `CHI-DataCenter` building, all Arista, with 4 redundant leaf uplinks
  (2 to each of 2 spines).
