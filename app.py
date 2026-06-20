import streamlit as st
import json
import pandas as pd
import io
import requests
from pathlib import Path

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NetOps Switch Manager",
    page_icon="🔌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Config ─────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent

def load_config():
    config_path = DATA_DIR / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}

CONFIG = load_config()
API_CFG = CONFIG.get("api", {})

def _api_headers():
    auth = API_CFG.get("auth", {})
    headers = {}
    if auth.get("type") == "bearer" and auth.get("token"):
        headers["Authorization"] = f"Bearer {auth['token']}"
    elif auth.get("type") == "api_key" and auth.get("api_key"):
        headers[auth.get("api_key_header", "X-API-Key")] = auth["api_key"]
    return headers

def _fetch_json(url):
    resp = requests.get(url, headers=_api_headers(), timeout=API_CFG.get("timeout_seconds", 10))
    resp.raise_for_status()
    return resp.json()

def _normalize(data, entity):
    """Hook for field name mapping when API shape differs from local JSON."""
    # data is a list of dicts; add remapping here once the real API shape is known
    return data

# ── Load data ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=API_CFG.get("cache_ttl_seconds", 300))
def load_data():
    base_url = API_CFG.get("base_url", "").strip()
    endpoints = API_CFG.get("endpoints", {})

    if base_url:
        try:
            switches = _normalize(_fetch_json(base_url + endpoints.get("switches", "/switches")), "switches")
            ports    = _normalize(_fetch_json(base_url + endpoints.get("ports",    "/ports")),    "ports")
            vlans    = _normalize(_fetch_json(base_url + endpoints.get("vlans",    "/vlans")),    "vlans")
            source = "api"
        except Exception as e:
            st.warning(f"API unavailable ({e}) — falling back to local data.")
            switches, ports, vlans, source = _load_static()
    else:
        switches, ports, vlans, source = _load_static()

    return pd.DataFrame(switches), pd.DataFrame(ports), pd.DataFrame(vlans), source

def _load_static():
    with open(DATA_DIR / "switches.json") as f:
        switches = json.load(f)
    with open(DATA_DIR / "ports.json") as f:
        ports = json.load(f)
    with open(DATA_DIR / "vlans.json") as f:
        vlans = json.load(f)
    return switches, ports, vlans, "static"

sw_df, port_df, vlan_df, data_source = load_data()

# ── Persistent description edits (session state) ───────────────────────────────
if "desc_edits" not in st.session_state:
    st.session_state.desc_edits = {}   # key: (hostname, port_name) → new description

def get_description(hostname, port_name, original):
    return st.session_state.desc_edits.get((hostname, port_name), original)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Palette: dark navy base, electric-cyan accent, amber warning */
:root {
    --navy:   #0d1b2a;
    --panel:  #1a2c42;
    --border: #2e4a6a;
    --cyan:   #00d4ff;
    --amber:  #f5a623;
    --red:    #e84040;
    --green:  #2ecc71;
    --text:   #cdd9e5;
    --muted:  #7a9ab8;
}
.stApp { background-color: var(--navy); color: var(--text); }
section[data-testid="stSidebar"] { background-color: var(--panel) !important; }
section[data-testid="stSidebar"] * { color: var(--text) !important; }

/* Metric cards */
div[data-testid="metric-container"] {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 16px;
}
div[data-testid="metric-container"] label { color: var(--muted) !important; font-size: 0.75rem; letter-spacing: .08em; text-transform: uppercase; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color: var(--cyan) !important; font-size: 1.8rem; font-family: 'Courier New', monospace; }

/* Section headers */
.section-header {
    font-family: 'Courier New', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--cyan);
    border-bottom: 1px solid var(--border);
    padding-bottom: 6px;
    margin: 18px 0 10px 0;
}

/* Status badges */
.badge-up   { background:#1a4a2e; color:#2ecc71; border:1px solid #2ecc71; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-family:monospace; }
.badge-down { background:#4a1a1a; color:#e84040; border:1px solid #e84040; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-family:monospace; }
.badge-trunk  { background:#1a2e4a; color:#00d4ff; border:1px solid #00d4ff; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-family:monospace; }
.badge-access { background:#2a1a4a; color:#a78bfa; border:1px solid #a78bfa; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-family:monospace; }
.badge-cisco  { background:#1a3a5c; color:#60a5fa; border:1px solid #60a5fa; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-family:monospace; }
.badge-arista { background:#1a4a3a; color:#34d399; border:1px solid #34d399; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-family:monospace; }

/* Switch card */
.sw-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
    cursor: pointer;
    transition: border-color .15s;
}
.sw-card:hover { border-color: var(--cyan); }
.sw-card .sw-hostname { font-family: 'Courier New', monospace; font-size: 1rem; color: var(--cyan); font-weight: bold; }
.sw-card .sw-meta    { font-size: 0.78rem; color: var(--muted); margin-top: 4px; }

/* Dataframe tweaks */
.stDataFrame { border: 1px solid var(--border) !important; border-radius: 6px; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { background: var(--panel); border-radius: 6px; }
.stTabs [data-baseweb="tab"] { color: var(--muted) !important; }
.stTabs [aria-selected="true"] { color: var(--cyan) !important; border-bottom: 2px solid var(--cyan) !important; }

/* Input fields */
.stTextInput input, .stSelectbox select, .stMultiSelect div {
    background: var(--panel) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
}

/* Sidebar nav style */
.nav-label {
    font-family: 'Courier New', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 16px 0 6px 0;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔌 NetOps")
    st.markdown("<div class='nav-label'>Navigation</div>", unsafe_allow_html=True)

    nav_pages = ["Dashboard", "Switch Browser", "Port Viewer", "VLAN Explorer", "Export"]
    nav_override = st.session_state.pop("nav_override", None)
    if nav_override and nav_override in nav_pages:
        st.session_state["page_radio"] = nav_override

    page = st.radio(
        "", nav_pages,
        label_visibility="collapsed",
        key="page_radio",
    )
    st.markdown("---")
    if data_source == "api":
        st.markdown("<span style='color:#2ecc71;font-size:0.75rem;'>● Live API</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span style='color:#f5a623;font-size:0.75rem;'>● Static files</span>", unsafe_allow_html=True)
    st.markdown("<div class='nav-label'>Quick Stats</div>", unsafe_allow_html=True)
    total_sw   = len(sw_df)
    total_port = len(port_df)
    ports_up   = (port_df["admin_status"] == "up").sum()
    st.markdown(f"**{total_sw}** switches")
    st.markdown(f"**{total_port:,}** total ports")
    st.markdown(f"**{ports_up:,}** ports admin-up")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.markdown("# NetOps Switch Manager")
    st.markdown("<div class='section-header'>Fleet Overview</div>", unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Total Switches", f"{len(sw_df)}")
    with c2: st.metric("Total Ports", f"{len(port_df):,}")
    with c3:
        up = (port_df["admin_status"] == "up").sum()
        st.metric("Ports Admin-Up", f"{up:,}")
    with c4:
        dn = (port_df["admin_status"] == "down").sum()
        st.metric("Ports Admin-Down", f"{dn:,}")
    with c5: st.metric("VLANs Defined", f"{len(vlan_df)}")

    # ── Level 1: Location summary ──────────────────────────────────────────────
    st.markdown("<div class='section-header'>Locations — click a row to drill in</div>", unsafe_allow_html=True)
    site_summary = sw_df.groupby("site").agg(
        Switches=("switch_id", "count"),
        Cisco=("manufacturer", lambda x: (x == "Cisco").sum()),
        Arista=("manufacturer", lambda x: (x == "Arista").sum()),
        City=("city", "first"),
    ).reset_index().sort_values("Switches", ascending=False).rename(columns={"site": "Site"})

    sel_site = st.dataframe(
        site_summary,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    # ── Level 2: Switches for selected location ────────────────────────────────
    chosen_site = None
    if sel_site and sel_site.selection.rows:
        chosen_site = site_summary.iloc[sel_site.selection.rows[0]]["Site"]

    if chosen_site:
        st.markdown(f"<div class='section-header'>Switches at {chosen_site} — click a row to see ports</div>", unsafe_allow_html=True)
        site_switches = sw_df[sw_df["site"] == chosen_site][
            ["hostname", "manufacturer", "model", "management_ip", "role", "building", "closet", "port_count"]
        ].copy()
        site_switches.columns = ["Hostname", "Vendor", "Model", "Mgmt IP", "Role", "Building", "Closet", "Ports"]

        sel_sw = st.dataframe(
            site_switches,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
        )

        # ── Level 3: Ports for selected switch ────────────────────────────────
        if sel_sw and sel_sw.selection.rows:
            chosen_hostname = site_switches.iloc[sel_sw.selection.rows[0]]["Hostname"]
            sw_ports = port_df[port_df["hostname"] == chosen_hostname].copy()

            # Merge VLAN name for access ports
            vlan_map = dict(zip(vlan_df["vlan_id"], vlan_df["name"]))

            def vlan_label(r):
                if r["mode"] == "access":
                    vid = r["access_vlan_id"]
                    name = vlan_map.get(vid, "")
                    return f"{vid} — {name}" if vid else "—"
                else:
                    allowed = r["allowed_vlans"]
                    if not allowed:
                        return "—"
                    parts = [f"{v}" for v in allowed[:4]]
                    suffix = f" +{len(allowed)-4} more" if len(allowed) > 4 else ""
                    native = r.get("native_vlan_id", "")
                    return f"Native:{native} | {', '.join(parts)}{suffix}"

            sw_ports["VLAN"] = sw_ports.apply(vlan_label, axis=1)

            display = sw_ports[["port_name", "admin_status", "oper_status", "mode", "VLAN", "description", "speed", "mac_count"]].copy()
            display.columns = ["Port", "Admin", "Oper", "Mode", "VLAN", "Description", "Speed", "MACs"]

            st.markdown(f"<div class='section-header'>Ports on {chosen_hostname} — {len(sw_ports)} total</div>", unsafe_allow_html=True)
            st.dataframe(display, use_container_width=True, hide_index=True)

            col_a, col_b = st.columns([1, 5])
            with col_a:
                if st.button("→ Open in Port Viewer", type="primary"):
                    st.session_state["selected_switch"] = chosen_hostname
                    st.session_state["nav_override"] = "Port Viewer"
                    st.rerun()
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("<div class='section-header'>By Role</div>", unsafe_allow_html=True)
            role_df = sw_df["role"].value_counts().reset_index()
            role_df.columns = ["Role", "Count"]
            st.dataframe(role_df, use_container_width=True, hide_index=True)
        with col2:
            st.markdown("<div class='section-header'>By Manufacturer</div>", unsafe_allow_html=True)
            mfr_df = sw_df["manufacturer"].value_counts().reset_index()
            mfr_df.columns = ["Manufacturer", "Count"]
            st.dataframe(mfr_df, use_container_width=True, hide_index=True)
        with col3:
            st.markdown("<div class='section-header'>By Chassis Type</div>", unsafe_allow_html=True)
            chassis_df = sw_df["chassis_type"].value_counts().reset_index()
            chassis_df.columns = ["Chassis Type", "Count"]
            st.dataframe(chassis_df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SWITCH BROWSER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Switch Browser":
    st.markdown("# Switch Browser")
    st.markdown("<div class='section-header'>Search & Filter</div>", unsafe_allow_html=True)

    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
    with col1:
        search = st.text_input("🔍 Search hostname or IP", placeholder="e.g. SW-NYC or 10.1.42")
    with col2:
        site_filter = st.selectbox("Site", ["All"] + sorted(sw_df["site"].unique().tolist()))
    with col3:
        role_filter = st.selectbox("Role", ["All"] + sorted(sw_df["role"].unique().tolist()))
    with col4:
        mfr_filter = st.selectbox("Manufacturer", ["All"] + sorted(sw_df["manufacturer"].unique().tolist()))
    with col5:
        chassis_filter = st.selectbox("Chassis Type", ["All"] + sorted(sw_df["chassis_type"].unique().tolist()))

    filtered = sw_df.copy()
    if search:
        mask = (
            filtered["hostname"].str.contains(search, case=False, na=False) |
            filtered["management_ip"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]
    if site_filter != "All":
        filtered = filtered[filtered["site"] == site_filter]
    if role_filter != "All":
        filtered = filtered[filtered["role"] == role_filter]
    if mfr_filter != "All":
        filtered = filtered[filtered["manufacturer"] == mfr_filter]
    if chassis_filter != "All":
        filtered = filtered[filtered["chassis_type"] == chassis_filter]

    st.markdown(f"<div class='section-header'>Results — {len(filtered)} switches</div>", unsafe_allow_html=True)

    if filtered.empty:
        st.info("No switches match your search criteria.")
    else:
        # Table view
        display_cols = ["hostname", "manufacturer", "model", "management_ip", "role", "site", "building", "closet", "chassis_type", "stack_members", "port_count", "os_version"]
        display_df = filtered[display_cols].copy()
        display_df["stack_members"] = display_df["stack_members"].apply(lambda x: int(x) if pd.notna(x) else "—")
        display_df.columns = ["Hostname", "Vendor", "Model", "Mgmt IP", "Role", "Site", "Building", "Closet", "Chassis", "Units", "Ports", "OS Version"]

        selected = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
        )

        # Detail panel for selected switch
        if selected and selected.selection.rows:
            row_idx = selected.selection.rows[0]
            sw = filtered.iloc[row_idx]

            st.markdown(f"<div class='section-header'>Switch Detail — {sw['hostname']}</div>", unsafe_allow_html=True)

            d1, d2, d3 = st.columns(3)
            with d1:
                mfr_badge = "badge-cisco" if sw["manufacturer"] == "Cisco" else "badge-arista"
                stack_str = f" ({int(sw['stack_members'])} units)" if pd.notna(sw["stack_members"]) else ""
                st.markdown(f"""
                **Hostname:** `{sw['hostname']}`  
                **Manufacturer:** <span class='{mfr_badge}'>{sw['manufacturer']}</span>  
                **Model:** `{sw['model']}`  
                **Chassis Type:** `{sw['chassis_type']}{stack_str}`  
                **OS / Version:** `{sw['os']} {sw['os_version']}`  
                **Serial:** `{sw['serial_number']}`
                """, unsafe_allow_html=True)
            with d2:
                st.markdown(f"""
                **Management IP:** `{sw['management_ip']}`  
                **Role:** `{sw['role'].capitalize()}`  
                **Fabric:** `{sw['fabric']}`  
                **Site:** `{sw['site']}` — {sw['city']}  
                **Building:** `{sw['building']}`  
                **Closet / Rack:** `{sw['closet']} / {sw['rack']}`
                """, unsafe_allow_html=True)
            with d3:
                sw_ports = port_df[port_df["hostname"] == sw["hostname"]]
                up_count = (sw_ports["admin_status"] == "up").sum()
                dn_count = (sw_ports["admin_status"] == "down").sum()
                trunk_count = (sw_ports["mode"] == "trunk").sum()
                multi_mac = (sw_ports["mac_count"] >= 2).sum()
                st.markdown(f"""
                **Total Ports:** `{sw['port_count']}`  
                **Admin-Up:** `{up_count}`  
                **Admin-Down:** `{dn_count}`  
                **Trunk Ports:** `{trunk_count}`  
                **Multi-device Ports (2+ MACs):** `{multi_mac}`  
                **Uptime:** `{sw['uptime_days']} days`
                """, unsafe_allow_html=True)

            if st.button("→ View Ports for this Switch", type="primary"):
                st.session_state["selected_switch"] = sw["hostname"]
                st.session_state["nav_override"] = "Port Viewer"
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PORT VIEWER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Port Viewer":

    st.markdown("# Port Viewer")

    # Switch selector
    col1, col2 = st.columns([3, 1])
    with col1:
        default_sw = st.session_state.get("selected_switch", sw_df["hostname"].iloc[0])
        sw_list = sorted(sw_df["hostname"].tolist())
        sw_idx = sw_list.index(default_sw) if default_sw in sw_list else 0
        selected_hostname = st.selectbox("Select Switch", sw_list, index=sw_idx)
        st.session_state["selected_switch"] = selected_hostname

    sw_info = sw_df[sw_df["hostname"] == selected_hostname].iloc[0]
    mfr_badge = "badge-cisco" if sw_info["manufacturer"] == "Cisco" else "badge-arista"
    stack_str = f" ({int(sw_info['stack_members'])}-unit stack)" if pd.notna(sw_info["stack_members"]) else ""

    st.markdown(f"""
    <div style='background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px 18px;margin:8px 0 14px 0;'>
    <span class='{mfr_badge}'>{sw_info['manufacturer']}</span>&nbsp;&nbsp;
    <code>{sw_info['model']}</code>&nbsp;&nbsp;|&nbsp;&nbsp;
    <code>{sw_info['management_ip']}</code>&nbsp;&nbsp;|&nbsp;&nbsp;
    {sw_info['site']} › {sw_info['building']} › {sw_info['closet']}&nbsp;&nbsp;|&nbsp;&nbsp;
    Role: <strong>{sw_info['role'].capitalize()}</strong>&nbsp;&nbsp;|&nbsp;&nbsp;
    Chassis: <strong>{sw_info['chassis_type']}{stack_str}</strong>
    </div>
    """, unsafe_allow_html=True)

    # Filters
    st.markdown("<div class='section-header'>Filters</div>", unsafe_allow_html=True)
    f1, f2, f3, f4, f5 = st.columns(5)
    with f1:
        admin_filter = st.selectbox("Admin Status", ["All", "up", "down"])
    with f2:
        oper_filter = st.selectbox("Oper Status", ["All", "up", "down"])
    with f3:
        mode_filter = st.selectbox("Port Mode", ["All", "access", "trunk"])
    with f4:
        uplink_filter = st.selectbox("Uplinks", ["All", "Uplinks only", "Non-uplinks only"])
    with f5:
        mac_filter = st.selectbox("MAC Count", ["All", "0 (empty)", "1 (single device)", "2+ (multi-device)", "10+ (high density)"])

    desc_search = st.text_input("🔍 Filter by description", placeholder="e.g. uplink, server, printer")

    sw_ports = port_df[port_df["hostname"] == selected_hostname].copy()

    # Apply description edits
    sw_ports["description"] = sw_ports.apply(
        lambda r: get_description(r["hostname"], r["port_name"], r["description"]), axis=1
    )

    if admin_filter != "All":
        sw_ports = sw_ports[sw_ports["admin_status"] == admin_filter]
    if oper_filter != "All":
        sw_ports = sw_ports[sw_ports["oper_status"] == oper_filter]
    if mode_filter != "All":
        sw_ports = sw_ports[sw_ports["mode"] == mode_filter]
    if uplink_filter == "Uplinks only":
        sw_ports = sw_ports[sw_ports["is_uplink"] == True]
    elif uplink_filter == "Non-uplinks only":
        sw_ports = sw_ports[sw_ports["is_uplink"] == False]

    if mac_filter == "0 (empty)":
        sw_ports = sw_ports[sw_ports["mac_count"] == 0]
    elif mac_filter == "1 (single device)":
        sw_ports = sw_ports[sw_ports["mac_count"] == 1]
    elif mac_filter == "2+ (multi-device)":
        sw_ports = sw_ports[sw_ports["mac_count"] >= 2]
    elif mac_filter == "10+ (high density)":
        sw_ports = sw_ports[sw_ports["mac_count"] >= 10]

    if desc_search:
        sw_ports = sw_ports[sw_ports["description"].str.contains(desc_search, case=False, na=False)]

    st.markdown(f"<div class='section-header'>Ports — {len(sw_ports)} shown</div>", unsafe_allow_html=True)

    slot_label = {
        "modular": "Slot (Line Card)",
        "stack": "Slot (Stack Unit)",
        "fixed": "Slot"
    }.get(sw_info["chassis_type"], "Slot")

    # Render port table with badges
    def render_ports(df):
        rows = []
        for _, r in df.iterrows():
            admin_badge = f"<span class='badge-up'>up</span>" if r["admin_status"] == "up" else f"<span class='badge-down'>down</span>"
            oper_badge  = f"<span class='badge-up'>up</span>" if r["oper_status"] == "up" else f"<span class='badge-down'>down</span>"
            mode_badge  = f"<span class='badge-trunk'>trunk</span>" if r["mode"] == "trunk" else f"<span class='badge-access'>access</span>"

            if r["mode"] == "access":
                vlan_info = f"VLAN {r['access_vlan_id']} ({r['access_vlan_name']})" if r["access_vlan_id"] else "—"
            else:
                allowed_str = ", ".join(str(v) for v in r["allowed_vlans"][:5]) if r["allowed_vlans"] else ""
                if r["allowed_vlans"] and len(r["allowed_vlans"]) > 5:
                    allowed_str += f" +{len(r['allowed_vlans'])-5} more"
                vlan_info = f"Native: {r['native_vlan_id']} | Allowed: {allowed_str}"

            mac = r.get("mac_count", 0)
            if mac == 0:
                mac_badge = "<span style='color:var(--muted)'>0</span>"
            elif mac == 1:
                mac_badge = "<span style='color:var(--green)'>1</span>"
            elif mac <= 9:
                mac_badge = f"<span style='color:var(--amber)'>{mac}</span>"
            else:
                mac_badge = f"<span style='color:var(--red);font-weight:bold'>{mac}</span>"

            rows.append({
                "Port":        r["port_name"],
                slot_label:    r["slot"] if r["slot"] is not None else "—",
                "Admin":       admin_badge,
                "Oper":        oper_badge,
                "Description": r["description"] or "—",
                "Mode":        mode_badge,
                "VLAN Info":   vlan_info,
                "MACs":        mac_badge,
                "Speed":       r["speed"],
                "Duplex":      r["duplex"],
                "Last Changed":r["last_changed"][:10],
            })
        return pd.DataFrame(rows)

    port_display = render_ports(sw_ports)

    st.write(
        port_display.to_html(escape=False, index=False),
        unsafe_allow_html=True
    )

    # ── Edit description ───────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Edit Port Description</div>", unsafe_allow_html=True)

    all_ports_for_sw = port_df[port_df["hostname"] == selected_hostname]["port_name"].tolist()
    ec1, ec2, ec3 = st.columns([2, 3, 1])
    with ec1:
        edit_port = st.selectbox("Port", all_ports_for_sw)
    with ec2:
        cur_row = port_df[(port_df["hostname"] == selected_hostname) & (port_df["port_name"] == edit_port)]
        cur_desc = get_description(selected_hostname, edit_port, cur_row["description"].iloc[0] if len(cur_row) else "")
        new_desc = st.text_input("New Description", value=cur_desc)
    with ec3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Save"):
            if data_source == "static":
                ports_path = DATA_DIR / "ports.json"
                with open(ports_path) as f:
                    all_ports = json.load(f)
                for p in all_ports:
                    if p["hostname"] == selected_hostname and p["port_name"] == edit_port:
                        p["description"] = new_desc
                        break
                with open(ports_path, "w") as f:
                    json.dump(all_ports, f, indent=2)
                load_data.clear()
                st.session_state.desc_edits.pop((selected_hostname, edit_port), None)
                st.success("Saved.")
            else:
                st.info("Read-only in API mode.")
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: VLAN EXPLORER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "VLAN Explorer":
    st.markdown("# VLAN Explorer")
    st.markdown("<div class='section-header'>VLAN Registry</div>", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])
    with col1:
        vlan_display = vlan_df.copy()
        vlan_display.columns = ["VLAN ID", "Name"]
        st.dataframe(vlan_display, use_container_width=True, hide_index=True)

    with col2:
        selected_vlan = st.selectbox("Select a VLAN to inspect", vlan_df["vlan_id"].tolist(),
                                     format_func=lambda v: f"{v} — {vlan_df[vlan_df['vlan_id']==v]['name'].iloc[0]}")

        st.markdown(f"<div class='section-header'>VLAN {selected_vlan} — Port Usage</div>", unsafe_allow_html=True)

        # Access ports on this VLAN
        access_ports = port_df[port_df["access_vlan_id"] == selected_vlan][["hostname","port_name","description","admin_status"]]
        # Trunk ports allowing this VLAN
        trunk_ports = port_df[
            port_df["allowed_vlans"].apply(lambda x: selected_vlan in x if isinstance(x, list) else False)
        ][["hostname","port_name","description","admin_status","native_vlan_id"]]

        t1, t2 = st.tabs([f"Access Ports ({len(access_ports)})", f"Trunk Ports ({len(trunk_ports)})"])
        with t1:
            if access_ports.empty:
                st.info("No access ports assigned to this VLAN.")
            else:
                st.dataframe(access_ports.rename(columns={
                    "hostname":"Switch","port_name":"Port","description":"Description","admin_status":"Admin"
                }), use_container_width=True, hide_index=True)
        with t2:
            if trunk_ports.empty:
                st.info("No trunk ports carry this VLAN.")
            else:
                st.dataframe(trunk_ports.rename(columns={
                    "hostname":"Switch","port_name":"Port","description":"Description",
                    "admin_status":"Admin","native_vlan_id":"Native VLAN"
                }), use_container_width=True, hide_index=True)

    st.markdown("<div class='section-header'>VLAN Usage Summary</div>", unsafe_allow_html=True)
    vlan_usage = []
    for _, v in vlan_df.iterrows():
        vid = v["vlan_id"]
        access_count = (port_df["access_vlan_id"] == vid).sum()
        trunk_count  = port_df["allowed_vlans"].apply(
            lambda x: vid in x if isinstance(x, list) else False
        ).sum()
        vlan_usage.append({"VLAN ID": vid, "Name": v["name"],
                           "Access Ports": access_count, "Trunk Ports": trunk_count,
                           "Total": access_count + trunk_count})
    usage_df = pd.DataFrame(vlan_usage).sort_values("Total", ascending=False)
    st.dataframe(usage_df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: EXPORT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Export":
    st.markdown("# Export Data")
    st.markdown("<div class='section-header'>Select Export Scope</div>", unsafe_allow_html=True)

    export_type = st.radio("What would you like to export?",
        ["All Ports (full fleet)", "Ports for a specific switch", "All Switches", "VLAN Registry"])

    export_df = None

    if export_type == "All Ports (full fleet)":
        export_df = port_df.copy()
        label = "all_ports"

    elif export_type == "Ports for a specific switch":
        sw_choice = st.selectbox("Select switch", sorted(sw_df["hostname"].tolist()))
        sw_ports = port_df[port_df["hostname"] == sw_choice].copy()
        sw_ports["description"] = sw_ports.apply(
            lambda r: get_description(r["hostname"], r["port_name"], r["description"]), axis=1
        )
        export_df = sw_ports
        label = sw_choice

    elif export_type == "All Switches":
        export_df = sw_df.copy()
        label = "all_switches"

    elif export_type == "VLAN Registry":
        export_df = vlan_df.copy()
        label = "vlans"

    if export_df is not None:
        st.markdown(f"<div class='section-header'>Preview — {len(export_df):,} rows</div>", unsafe_allow_html=True)
        st.dataframe(export_df.head(50), use_container_width=True, hide_index=True)
        if len(export_df) > 50:
            st.caption(f"Showing first 50 of {len(export_df):,} rows. Full dataset will be exported.")

        ec1, ec2 = st.columns(2)
        with ec1:
            csv_data = export_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_data,
                file_name=f"{label}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with ec2:
            try:
                from reportlab.lib.pagesizes import landscape, A4
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                from reportlab.lib import colors
                from reportlab.lib.styles import getSampleStyleSheet

                buf = io.BytesIO()
                doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
                styles = getSampleStyleSheet()
                elements = [Paragraph(f"NetOps Export: {label}", styles["Title"]), Spacer(1, 12)]

                preview = export_df.head(500)
                cols = list(preview.columns)
                data = [cols] + preview.values.tolist()
                # Truncate long strings
                data = [[str(c)[:30] if isinstance(c, (list, str)) else str(c) for c in row] for row in data]

                t = Table(data, repeatRows=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a2c42")),
                    ("TEXTCOLOR",  (0,0), (-1,0), colors.HexColor("#00d4ff")),
                    ("FONTSIZE",   (0,0), (-1,-1), 6),
                    ("GRID",       (0,0), (-1,-1), 0.25, colors.HexColor("#2e4a6a")),
                    ("BACKGROUND", (0,1), (-1,-1), colors.HexColor("#0d1b2a")),
                    ("TEXTCOLOR",  (0,1), (-1,-1), colors.HexColor("#cdd9e5")),
                    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#0d1b2a"), colors.HexColor("#111f30")]),
                ]))
                elements.append(t)
                doc.build(elements)
                buf.seek(0)
                st.download_button(
                    label="⬇️ Download PDF",
                    data=buf,
                    file_name=f"{label}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except ImportError:
                st.warning("PDF export requires `reportlab`. Run: `pip install reportlab`")
