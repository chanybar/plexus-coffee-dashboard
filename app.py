import json
import uuid
from datetime import date, datetime
from io import StringIO

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Plexus Coffee Tracker",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme + styling ───────────────────────────────────────────────────
st.markdown(
    """
<style>
:root {
  --bg: #f6efe5;
  --panel: rgba(255,255,255,0.72);
  --panel-2: rgba(255,255,255,0.58);
  --text: #2f251d;
  --muted: #6c5a4d;
  --line: rgba(111,78,55,0.14);
  --hero-a: #6f4e37;
  --hero-b: #c88642;
  --green: #2f7d57;
  --orange: #c67b2c;
  --amber: #9a6a3a;
  --red: #d64545;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f1115;
    --panel: rgba(24,28,34,0.86);
    --panel-2: rgba(21,24,30,0.92);
    --text: #f3ede5;
    --muted: #b9ab9b;
    --line: rgba(255,255,255,0.08);
    --hero-a: #4d3426;
    --hero-b: #9f6431;
    --green: #3f9c70;
    --orange: #db8e38;
    --amber: #b98554;
    --red: #ef5b5b;
  }
}

.stApp {
  background: radial-gradient(circle at top left, rgba(200,134,66,0.11), transparent 28%),
              linear-gradient(180deg, var(--bg) 0%, var(--bg) 100%);
  color: var(--text);
}
section[data-testid="stSidebar"] {
  background: var(--panel-2);
  border-right: 1px solid var(--line);
}
.block-container {
  padding-top: 1.6rem;
  padding-bottom: 3rem;
}
h1,h2,h3,h4 {
  color: var(--text) !important;
  letter-spacing: -0.02em;
}
.hero {
  background: linear-gradient(120deg, var(--hero-a) 0%, var(--hero-b) 100%);
  color: #fff8f0;
  padding: 1.4rem 1.6rem;
  border-radius: 24px;
  margin-bottom: 1rem;
  box-shadow: 0 18px 50px rgba(0,0,0,0.14);
}
.hero h1 {
  color: #fff8f0 !important;
  margin: 0;
  font-size: 2.05rem;
}
.hero p {
  margin: 0.45rem 0 0 0;
  color: #f5e8dc;
  font-size: 0.98rem;
}
.card {
  background: var(--panel);
  backdrop-filter: blur(10px);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 1rem 1rem 0.9rem 1rem;
  box-shadow: 0 12px 30px rgba(0,0,0,0.06);
}
.kpi-card {
  background: var(--panel);
  backdrop-filter: blur(10px);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 0.95rem 1rem;
  min-height: 102px;
}
.kpi-label {
  color: var(--muted);
  font-size: 0.85rem;
  margin-bottom: 0.18rem;
}
.kpi-value {
  color: var(--text);
  font-weight: 800;
  font-size: 1.85rem;
}
.small-note {
  color: var(--muted);
  font-size: 0.92rem;
}
.route-pill {
  display:inline-block;
  padding:0.27rem 0.62rem;
  border-radius:999px;
  margin:0 0.35rem 0.35rem 0;
  border:1px solid var(--line);
  background: rgba(198,123,44,0.10);
  color: var(--text);
  font-size:0.82rem;
}
.metric-inline {
  color: var(--muted);
  font-size: 0.9rem;
}
.leaflet-container {
  border-radius: 18px;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Seed loading ──────────────────────────────────────────────────────
@st.cache_data
def load_seed():
    with open("data.json", "r", encoding="utf-8") as f:
        return json.load(f)


def init_state() -> None:
    if "stops" not in st.session_state:
        seed = load_seed()
        st.session_state.stops = seed["stops"]
        st.session_state.routes = seed["routes"]
        st.session_state.wb_adj = seed["beans"].get("wb_adj", 0)
        st.session_state.gc_adj = seed["beans"].get("gc_adj", 0)
    if "route_uploads" not in st.session_state:
        st.session_state.route_uploads = []
    if "route_upload_counter" not in st.session_state:
        st.session_state.route_upload_counter = 0


init_state()

# ── Constants ─────────────────────────────────────────────────────────
STAR_COLOR = {3: "#2f7d57", 2: "#c67b2c", 1: "#9a6a3a", 0: "#d64545"}
STAR_LABEL = {3: "⭐⭐⭐", 2: "⭐⭐", 1: "⭐", 0: "0 Star"}
STATUS_COLOR = {"Pending": "#d64545", "In Route": "#c67b2c", "Completed": "#2f7d57"}
CATEGORIES = [
    "Law", "Architecture", "Construction", "Biotech", "Finance",
    "Healthcare", "Real Estate", "Other"
]

# ── Helpers ───────────────────────────────────────────────────────────
def normalize_stop_dict(stop: dict) -> dict:
    stop = dict(stop)
    stop.setdefault("address", "")
    stop.setdefault("contact", "")
    stop.setdefault("route_status", "Completed")
    stop.setdefault("source_upload_id", "")
    stop.setdefault("lat", None)
    stop.setdefault("lng", None)
    return stop


def normalize_plan_dict(plan: dict) -> dict:
    plan = dict(plan)
    plan.setdefault("address", "")
    plan.setdefault("cat", "Other")
    plan.setdefault("contact", "")
    plan.setdefault("notes", "")
    plan.setdefault("lat", None)
    plan.setdefault("lng", None)
    plan.setdefault("status", "Pending")
    return plan


def stops_df() -> pd.DataFrame:
    rows = [normalize_stop_dict(s) for s in st.session_state.stops]
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=[
            "id", "route_id", "date", "stop", "company", "cat", "lat", "lng",
            "stars", "wb", "gc", "notes", "address", "contact", "route_status",
            "source_upload_id"
        ])
    df["date"] = df["date"].astype(str)
    return df


def route_plans_df() -> pd.DataFrame:
    rows = [normalize_plan_dict(r) for r in st.session_state.route_uploads]
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=[
            "upload_id", "date", "company", "address", "cat", "contact",
            "notes", "status", "lat", "lng"
        ])
    df["date"] = df["date"].astype(str)
    return df


def route_name_for(route_id: str, route_date: str) -> str:
    for route in st.session_state.routes:
        if route["id"] == route_id:
            return route["name"]
    for route in st.session_state.routes:
        if route["date"] == route_date:
            return route["name"]
    return f"Route {route_date}"


def ensure_route(date_str: str, preferred_name: str | None = None) -> str:
    for route in st.session_state.routes:
        if route["date"] == date_str:
            if preferred_name and not route.get("name"):
                route["name"] = preferred_name
            return route["id"]
    route_id = f"r-{uuid.uuid4().hex[:8]}"
    st.session_state.routes.append({
        "id": route_id,
        "date": date_str,
        "name": preferred_name or f"Route {date_str}",
    })
    return route_id


def known_coordinate_lookup() -> dict:
    known: dict[str, tuple[float, float]] = {}
    for _, row in stops_df().iterrows():
        lat, lng = row.get("lat"), row.get("lng")
        if pd.notna(lat) and pd.notna(lng):
            company = str(row.get("company", "")).strip().lower()
            address = str(row.get("address", "")).strip().lower()
            if company:
                known[f"company::{company}"] = (float(lat), float(lng))
            if address:
                known[f"address::{address}"] = (float(lat), float(lng))
    for _, row in route_plans_df().iterrows():
        lat, lng = row.get("lat"), row.get("lng")
        if pd.notna(lat) and pd.notna(lng):
            company = str(row.get("company", "")).strip().lower()
            address = str(row.get("address", "")).strip().lower()
            if company:
                known.setdefault(f"company::{company}", (float(lat), float(lng)))
            if address:
                known.setdefault(f"address::{address}", (float(lat), float(lng)))
    return known


def infer_coordinates(company: str, address: str, lat=None, lng=None) -> tuple[float | None, float | None]:
    if lat not in (None, "") and lng not in (None, ""):
        try:
            return float(lat), float(lng)
        except Exception:
            pass
    known = known_coordinate_lookup()
    ckey = f"company::{str(company).strip().lower()}"
    akey = f"address::{str(address).strip().lower()}"
    if ckey in known:
        return known[ckey]
    if akey in known:
        return known[akey]
    return None, None


def total_stops_count(df: pd.DataFrame | None = None) -> int:
    base = stops_df() if df is None else df
    return int(len(base))


def total_whole_bean(df: pd.DataFrame | None = None) -> int:
    base = stops_df() if df is None else df
    total = int(base["wb"].fillna(0).sum()) if not base.empty else 0
    if df is None:
        total += int(st.session_state.wb_adj)
    return total


def total_ground_coffee(df: pd.DataFrame | None = None) -> int:
    base = stops_df() if df is None else df
    ground = max(total_stops_count(base) - int(base["wb"].fillna(0).sum()), 0)
    if df is None:
        ground += int(st.session_state.gc_adj)
    return int(ground)


def completion_rate() -> float:
    plans = route_plans_df()
    if plans.empty:
        return 0.0
    done = int((plans["status"] == "Completed").sum())
    return round(done / len(plans) * 100, 1)


def todays_summary(date_str: str) -> tuple[int, int, int]:
    df = stops_df()
    day = df[df["date"] == date_str]
    if day.empty:
        return 0, 0, 0
    return len(day), int(day["wb"].sum()), max(len(day) - int(day["wb"].sum()), 0)


def route_performance_df() -> pd.DataFrame:
    df = stops_df()
    if df.empty:
        return pd.DataFrame(columns=["Date", "Route", "Stops", "3-Star", "WB", "Ground", "Completion Score"])
    rows = []
    for dt in sorted(df["date"].unique().tolist(), reverse=True):
        day = df[df["date"] == dt]
        route_id = day.iloc[0]["route_id"] if not day.empty else ""
        route_name = route_name_for(route_id, dt)
        rows.append({
            "Date": dt,
            "Route": route_name,
            "Stops": len(day),
            "3-Star": int((day["stars"] == 3).sum()),
            "WB": int(day["wb"].sum()),
            "Ground": max(len(day) - int(day["wb"].sum()), 0),
            "Completion Score": round(((day["stars"] * 10).sum()) / max(len(day), 1), 1),
        })
    return pd.DataFrame(rows)


def render_kpi(label: str, value: str | int, help_text: str | None = None) -> None:
    st.markdown(
        f"<div class='kpi-card'><div class='kpi-label'>{label}</div><div class='kpi-value'>{value}</div>"
        + (f"<div class='small-note'>{help_text}</div>" if help_text else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def export_payload() -> dict:
    return {
        "stops": [normalize_stop_dict(s) for s in st.session_state.stops],
        "routes": st.session_state.routes,
        "beans": {"wb_adj": st.session_state.wb_adj, "gc_adj": st.session_state.gc_adj},
        "route_uploads": [normalize_plan_dict(r) for r in st.session_state.route_uploads],
    }

# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ☕ Plexus Coffee Tracker")
    st.caption("Analytical field tracker")
    page = st.radio(
        "Navigate",
        ["📊 Overview", "🗺️ Map", "📋 Stop Log", "➕ Add Stop", "📝 Route Plans", "🫘 Bean Tracker"],
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown(f"**Stops:** {total_stops_count()}  ")
    st.markdown(f"**Whole Bean:** {total_whole_bean()}  ")
    st.markdown(f"**Ground:** {total_ground_coffee()}  ")
    st.markdown(f"**Bags Given:** {total_stops_count()}  ")
    st.caption(f"{len(st.session_state.routes)} routes · {completion_rate()}% planned completion")
    st.divider()
    st.download_button(
        "⬇ Export Dashboard Data",
        data=json.dumps(export_payload(), indent=2),
        file_name="coffee_tracker_data.json",
        mime="application/json",
        use_container_width=True,
    )
    uploaded = st.file_uploader("⬆ Import Dashboard Data", type="json", label_visibility="collapsed")
    if uploaded:
        data = json.load(uploaded)
        st.session_state.stops = data.get("stops", [])
        st.session_state.routes = data.get("routes", [])
        beans = data.get("beans", {})
        st.session_state.wb_adj = beans.get("wb_adj", 0)
        st.session_state.gc_adj = beans.get("gc_adj", 0)
        st.session_state.route_uploads = data.get("route_uploads", [])
        st.success("Dashboard data imported.")
        st.rerun()

# ── Overview ──────────────────────────────────────────────────────────
if page == "📊 Overview":
    df = stops_df()
    plans = route_plans_df()
    today = date.today().strftime("%Y-%m-%d")
    today_stops, today_wb, today_ground = todays_summary(today)

    st.markdown(
        """
        <div class='hero'>
          <h1>Plexus Coffee Overview</h1>
          <p>Track route execution, outreach quality, and coffee distribution in one place. This is your command center for performance, planning, and follow-up.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi("Total Stops", total_stops_count(), "All logged visits")
    with k2: render_kpi("Bags Given", total_stops_count(), "Stops = total bags")
    with k3: render_kpi("Whole Bean", total_whole_bean(), "Logged whole bean + adjustment")
    with k4: render_kpi("Ground Coffee", total_ground_coffee(), "Remaining bags not marked whole bean")

    k5, k6, k7, k8 = st.columns(4)
    with k5: render_kpi("3-Star Stops", int((df["stars"] == 3).sum()) if not df.empty else 0)
    with k6: render_kpi("2-Star Stops", int((df["stars"] == 2).sum()) if not df.empty else 0)
    with k7: render_kpi("1-Star Stops", int((df["stars"] == 1).sum()) if not df.empty else 0)
    with k8: render_kpi("0-Star / Planned Risk", (int((df["stars"] == 0).sum()) if not df.empty else 0) + int((plans["status"] != "Completed").sum()) if not plans.empty else 0)

    k9, k10, k11, k12 = st.columns(4)
    with k9: render_kpi("Today Stops", today_stops)
    with k10: render_kpi("Today Whole Bean", today_wb)
    with k11: render_kpi("Today Ground", today_ground)
    with k12: render_kpi("Plan Completion", f"{completion_rate()}%", "Completed / total planned stops")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Star Distribution")
        star_data = pd.DataFrame({
            "Rating": ["0 Star", "1 Star", "2 Stars", "3 Stars"],
            "Count": [
                int((df["stars"] == 0).sum()) if not df.empty else 0,
                int((df["stars"] == 1).sum()) if not df.empty else 0,
                int((df["stars"] == 2).sum()) if not df.empty else 0,
                int((df["stars"] == 3).sum()) if not df.empty else 0,
            ],
        })
        fig = px.bar(
            star_data,
            x="Rating",
            y="Count",
            text="Count",
            color="Rating",
            color_discrete_map={
                "0 Star": STAR_COLOR[0],
                "1 Star": STAR_COLOR[1],
                "2 Stars": STAR_COLOR[2],
                "3 Stars": STAR_COLOR[3],
            },
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            showlegend=False,
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="rgba(127,127,127,0.16)"),
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Bags by Route Day")
        perf = route_performance_df()
        if not perf.empty:
            line = px.line(
                perf.sort_values("Date"),
                x="Date",
                y="Stops",
                markers=True,
                color_discrete_sequence=["#c88642"],
            )
            line.update_layout(
                height=320,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(gridcolor="rgba(127,127,127,0.16)"),
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(line, use_container_width=True)
        else:
            st.info("No route data yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    c3, c4 = st.columns([1.15, 1])
    with c3:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Top Analytical View")
        perf = route_performance_df()
        if not perf.empty:
            st.dataframe(perf, use_container_width=True, hide_index=True)
        else:
            st.info("Route performance will appear once stops are logged.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c4:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Recent Stops")
        recent = df.sort_values(["date", "stop"], ascending=[False, False]).head(8) if not df.empty else pd.DataFrame()
        if not recent.empty:
            for _, s in recent.iterrows():
                st.markdown(
                    f"**{s['company']}** · {STAR_LABEL.get(int(s['stars']), '—')}  \n"
                    f"<span class='small-note'>{s['date']} · {route_name_for(s['route_id'], s['date'])} · {s['cat']}</span>  \n"
                    f"<span class='small-note'>{s.get('notes', '') or 'No notes added.'}</span>",
                    unsafe_allow_html=True,
                )
                st.divider()
        else:
            st.info("No stops yet.")
        st.markdown("</div>", unsafe_allow_html=True)

# ── Map ───────────────────────────────────────────────────────────────
elif page == "🗺️ Map":
    df = stops_df()
    plans = route_plans_df()

    st.markdown(
        """
        <div class='hero'>
          <h1>Route Map</h1>
          <p>Use this to view completed stops, low-quality stops, and pending route-plan locations. 0-star points show in red. Planned stops stay visible until they are completed.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    date_options = ["All Days"] + sorted(set(df["date"].tolist() + plans["date"].tolist()), reverse=True)
    m1, m2, m3 = st.columns([1, 1, 1])
    selected_day = m1.selectbox("View route day", date_options)
    star_filter = m2.multiselect(
        "Filter by rating",
        [0, 1, 2, 3],
        default=[0, 1, 2, 3],
        format_func=lambda x: STAR_LABEL[x],
    )
    category_options = sorted(set(df["cat"].dropna().tolist() + plans["cat"].dropna().tolist()))
    selected_categories = m3.multiselect("Filter by industry", category_options, default=category_options)

    actual = df.copy()
    planned = plans[plans["status"].isin(["Pending", "In Route"])].copy() if not plans.empty else plans.copy()

    if selected_day != "All Days":
        actual = actual[actual["date"] == selected_day]
        planned = planned[planned["date"] == selected_day]

    if selected_categories:
        actual = actual[actual["cat"].isin(selected_categories)]
        planned = planned[planned["cat"].isin(selected_categories)]

    actual = actual[actual["stars"].isin(star_filter)]
    if 0 not in star_filter:
        planned = planned.iloc[0:0]

    actual_map = actual[actual["lat"].notna() & actual["lng"].notna()]
    planned_map = planned[planned["lat"].notna() & planned["lng"].notna()]

    fmap = folium.Map(location=[33.480, -111.980], zoom_start=11, tiles="CartoDB positron")

    for _, s in actual_map.iterrows():
        popup_html = f"""
        <div style='font-family: sans-serif; min-width: 220px;'>
          <b>{s['company']}</b><br>
          <small>{s['date']} · {route_name_for(s['route_id'], s['date'])}</small><br>
          <small>{s['cat']} · {STAR_LABEL.get(int(s['stars']), '—')}</small><br>
          <small>WB: {int(s['wb'])} · Ground: {max(1 - int(s['wb']), 0)}</small><br>
          <small>{s.get('notes', '') or 'No notes added.'}</small>
        </div>
        """
        folium.CircleMarker(
            location=[float(s["lat"]), float(s["lng"])],
            radius=10,
            color="white",
            weight=2.4,
            fill=True,
            fill_color=STAR_COLOR.get(int(s["stars"]), "#999999"),
            fill_opacity=0.95,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=s["company"],
        ).add_to(fmap)

    for _, s in planned_map.iterrows():
        popup_html = f"""
        <div style='font-family: sans-serif; min-width: 220px;'>
          <b>{s['company']}</b><br>
          <small>{s['date']} · {s['status']}</small><br>
          <small>{s['cat']} · 0 Star planned stop</small><br>
          <small>{s.get('address', '')}</small>
        </div>
        """
        folium.CircleMarker(
            location=[float(s["lat"]), float(s["lng"])],
            radius=9,
            color="white",
            weight=2.0,
            fill=True,
            fill_color=STATUS_COLOR.get(s["status"], STAR_COLOR[0]),
            fill_opacity=0.90,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"{s['status']}: {s['company']}",
        ).add_to(fmap)

    st_folium(fmap, width=None, height=630, returned_objects=[])
    st.caption(
        f"Mapped completed stops: {len(actual_map)} · Mapped pending / in-route planned stops: {len(planned_map)} · Missing coordinates: {len(actual) - len(actual_map)} actual, {len(planned) - len(planned_map)} planned"
    )

# ── Stop Log ──────────────────────────────────────────────────────────
elif page == "📋 Stop Log":
    df = stops_df()
    st.markdown(
        """
        <div class='hero'>
          <h1>Stop Log</h1>
          <p>This tab is your full field history. Use it to review every day you ran, what route it belonged to, which businesses were strongest, what coffee was given out, what happened at each stop, and what needs a follow-up.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df.empty:
        st.info("No stops logged yet.")
    else:
        f1, f2, f3, f4 = st.columns([1.15, 1, 1, 1.2])
        day_filter = f1.selectbox("Filter by day", ["All Days"] + sorted(df["date"].unique().tolist(), reverse=True))
        star_filter = f2.selectbox("Filter by stars", ["All", "0", "1", "2", "3"])
        cat_filter = f3.selectbox("Filter by industry", ["All"] + sorted(df["cat"].dropna().unique().tolist()))
        search = f4.text_input("Search", placeholder="Company, address, notes")

        filtered = df.copy()
        if day_filter != "All Days":
            filtered = filtered[filtered["date"] == day_filter]
        if star_filter != "All":
            filtered = filtered[filtered["stars"] == int(star_filter)]
        if cat_filter != "All":
            filtered = filtered[filtered["cat"] == cat_filter]
        if search:
            mask = (
                filtered["company"].str.contains(search, case=False, na=False)
                | filtered["address"].str.contains(search, case=False, na=False)
                | filtered["notes"].str.contains(search, case=False, na=False)
            )
            filtered = filtered[mask]

        filtered = filtered.sort_values(["date", "stop"], ascending=[False, True])
        st.caption(f"{len(filtered)} stops shown")

        for dt in filtered["date"].drop_duplicates():
            day_df = filtered[filtered["date"] == dt].copy()
            with st.expander(f"{dt} · {len(day_df)} stops", expanded=(day_filter != "All Days")):
                route_names = sorted(set(day_df.apply(lambda x: route_name_for(x["route_id"], x["date"]), axis=1).tolist()))
                if route_names:
                    st.markdown("".join([f"<span class='route-pill'>{name}</span>" for name in route_names]), unsafe_allow_html=True)
                display = day_df[["stop", "company", "cat", "stars", "wb", "address", "notes"]].copy()
                display["stars"] = display["stars"].apply(lambda x: STAR_LABEL.get(int(x), "—"))
                display["ground"] = display["wb"].apply(lambda x: max(1 - int(x), 0))
                display.columns = ["Stop #", "Company", "Industry", "Rating", "Whole Bean", "Address", "Notes", "Ground"]
                display = display[["Stop #", "Company", "Industry", "Rating", "Whole Bean", "Ground", "Address", "Notes"]]
                st.dataframe(display, use_container_width=True, hide_index=True)

# ── Add Stop ──────────────────────────────────────────────────────────
elif page == "➕ Add Stop":
    df = stops_df()
    plans = route_plans_df()
    st.markdown(
        """
        <div class='hero'>
          <h1>Add Stop</h1>
          <p>Log a stop fast. If the stop was already in your route plan or a company has been mapped before, the app reuses those coordinates automatically so the stop can appear on the map without manual lat/lng entry.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_form, col_day = st.columns([1.35, 1])
    with col_form:
        with st.form("add_stop_form", clear_on_submit=True):
            date_cols = st.columns(2)
            route_date = date_cols[0].date_input("Date", value=date.today())
            date_str = route_date.strftime("%Y-%m-%d")
            existing = next((r for r in st.session_state.routes if r["date"] == date_str), None)
            route_name = date_cols[1].text_input("Route Name", value=existing["name"] if existing else "")

            day_plans = plans[(plans["date"] == date_str) & (plans["status"] != "Completed")].copy() if not plans.empty else pd.DataFrame()
            plan_labels = {"Manual entry": None}
            if not day_plans.empty:
                for _, row in day_plans.iterrows():
                    plan_labels[f"{row['company']} · {row.get('address', '')}"] = row["upload_id"]
            selected_label = st.selectbox("Planned stop", list(plan_labels.keys()))
            selected_plan = None
            if plan_labels[selected_label] is not None:
                selected_plan = day_plans[day_plans["upload_id"] == plan_labels[selected_label]].iloc[0]

            company = st.text_input("Company Name *", value="" if selected_plan is None else str(selected_plan.get("company", "")))
            default_cat_index = CATEGORIES.index(selected_plan["cat"]) if selected_plan is not None and selected_plan.get("cat") in CATEGORIES else 0
            cat = st.selectbox("Industry", CATEGORIES, index=default_cat_index)
            address = st.text_input("Address", value="" if selected_plan is None else str(selected_plan.get("address", "")))
            contact = st.text_input("Contact Name", value="" if selected_plan is None else str(selected_plan.get("contact", "")))

            s1, s2 = st.columns([1.1, 1])
            stars = s1.radio("Rating", [0, 1, 2, 3], index=2, format_func=lambda x: STAR_LABEL[x], horizontal=True)
            wb = s2.number_input("Whole Bean bags", min_value=0, max_value=10, value=0, step=1)
            notes = st.text_area("Notes", value="" if selected_plan is None else str(selected_plan.get("notes", "")), placeholder="What happened? Any key details...")
            status = st.selectbox("Route Status", ["Completed", "In Route", "Pending"], index=0)
            submitted = st.form_submit_button("✅ Save Stop", use_container_width=True)

        if submitted:
            if not company.strip():
                st.warning("Company name is required.")
            else:
                route_id = ensure_route(date_str, route_name.strip() or None)
                fallback_lat = selected_plan.get("lat") if selected_plan is not None else None
                fallback_lng = selected_plan.get("lng") if selected_plan is not None else None
                lat, lng = infer_coordinates(company.strip(), address.strip(), fallback_lat, fallback_lng)
                stops_today = df[df["date"] == date_str] if not df.empty else pd.DataFrame()
                st.session_state.stops.append({
                    "id": f"s-{uuid.uuid4().hex[:8]}",
                    "route_id": route_id,
                    "date": date_str,
                    "stop": len(stops_today) + 1,
                    "company": company.strip(),
                    "cat": cat,
                    "lat": lat,
                    "lng": lng,
                    "stars": int(stars),
                    "wb": int(wb),
                    "gc": max(1 - int(wb), 0),
                    "notes": notes.strip(),
                    "address": address.strip(),
                    "contact": contact.strip(),
                    "route_status": status,
                    "source_upload_id": "" if selected_plan is None else str(selected_plan["upload_id"]),
                })
                if selected_plan is not None:
                    for plan in st.session_state.route_uploads:
                        if plan["upload_id"] == str(selected_plan["upload_id"]):
                            plan["status"] = status if status != "Completed" else "Completed"
                st.success(f"Saved {company.strip()} for {date_str}.")
                st.rerun()

    with col_day:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Selected Day Snapshot")
        date_str = date.today().strftime("%Y-%m-%d")
        day = df[df["date"] == date_str].sort_values("stop") if not df.empty else pd.DataFrame()
        if not day.empty:
            for _, s in day.iterrows():
                st.markdown(
                    f"**{int(s['stop'])}. {s['company']}**  \n"
                    f"<span class='small-note'>{STAR_LABEL.get(int(s['stars']), '—')} · WB {int(s['wb'])} · Ground {max(1-int(s['wb']), 0)}</span>",
                    unsafe_allow_html=True,
                )
                st.divider()
            st.markdown(f"**Stops:** {len(day)}")
            st.markdown(f"**Whole Bean:** {int(day['wb'].sum())}")
            st.markdown(f"**Ground:** {max(len(day) - int(day['wb'].sum()), 0)}")
        else:
            st.caption("No stops logged yet today.")
        st.markdown("</div>", unsafe_allow_html=True)

# ── Route Plans ───────────────────────────────────────────────────────
elif page == "📝 Route Plans":
    plans = route_plans_df()
    st.markdown(
        """
        <div class='hero'>
          <h1>Route Plans</h1>
          <p>Have your marketing team build the daily route in Excel, Google Sheets, Airtable, or any cloud sheet. Export it as CSV and upload it here. The app cleans the file, turns it into planned stops, lets you mark each one Pending, In Route, or Completed, and uses any known coordinates to place those planned stops on the map.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Upload route CSV")
    st.caption("Recommended columns: date, company, address, cat, contact, notes, lat, lng")
    uploaded_csv = st.file_uploader("Upload route list", type=["csv"], key="route_csv_upload")
    if uploaded_csv is not None:
        try:
            text = StringIO(uploaded_csv.getvalue().decode("utf-8"))
            incoming = pd.read_csv(text)
            incoming.columns = [str(c).strip().lower() for c in incoming.columns]
            if not {"date", "company"}.issubset(set(incoming.columns)):
                st.error("CSV needs at least 'date' and 'company' columns.")
            else:
                normalized = incoming.copy()
                for col in ["address", "cat", "contact", "notes", "lat", "lng"]:
                    if col not in normalized.columns:
                        normalized[col] = ""
                normalized["cat"] = normalized["cat"].apply(lambda x: x if x in CATEGORIES else "Other")
                normalized["date"] = pd.to_datetime(normalized["date"]).dt.strftime("%Y-%m-%d")
                st.dataframe(normalized, use_container_width=True, hide_index=True)
                if st.button("Add uploaded route list", key="add_uploaded_route_list", type="primary"):
                    added = 0
                    for _, row in normalized.iterrows():
                        st.session_state.route_upload_counter += 1
                        lat, lng = infer_coordinates(row.get("company", ""), row.get("address", ""), row.get("lat", None), row.get("lng", None))
                        st.session_state.route_uploads.append({
                            "upload_id": f"u-{st.session_state.route_upload_counter}",
                            "date": row["date"],
                            "company": str(row.get("company", "")).strip(),
                            "address": str(row.get("address", "")).strip(),
                            "cat": str(row.get("cat", "Other")).strip() or "Other",
                            "contact": str(row.get("contact", "")).strip(),
                            "notes": str(row.get("notes", "")).strip(),
                            "status": "Pending",
                            "lat": lat,
                            "lng": lng,
                        })
                        ensure_route(row["date"])
                        added += 1
                    st.success(f"Added {added} planned stops.")
                    st.rerun()
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Quick-generate 10 stops for the day")
    st.caption("Use this when you want a fast working route plan to test with.")
    if st.button("Generate sample 10-stop route", key="generate_sample_route", use_container_width=True):
        base_date = date.today().strftime("%Y-%m-%d")
        samples = [
            ("Phoenix Law Firm — MSP Prospect", "Phoenix", "Law"),
            ("Snell & Wilmer", "Phoenix", "Law"),
            ("Greenberg Traurig Phoenix", "Phoenix", "Law"),
            ("Populous Phoenix", "Phoenix", "Architecture"),
            ("DWL Architects", "Phoenix", "Architecture"),
            ("Layton Construction", "Phoenix", "Construction"),
            ("Sundt Construction", "Phoenix", "Construction"),
            ("HKS Scottsdale", "Scottsdale", "Architecture"),
            ("RSP Architects Mesa", "Mesa", "Architecture"),
            ("MBS Biotechnology", "Mesa", "Biotech"),
        ]
        for name, addr, cat in samples:
            st.session_state.route_upload_counter += 1
            lat, lng = infer_coordinates(name, addr)
            st.session_state.route_uploads.append({
                "upload_id": f"u-{st.session_state.route_upload_counter}",
                "date": base_date,
                "company": name,
                "address": addr,
                "cat": cat,
                "contact": "",
                "notes": "Auto-generated sample route",
                "status": "Pending",
                "lat": lat,
                "lng": lng,
            })
        ensure_route(base_date, preferred_name=f"Generated Route {base_date}")
        st.success("Generated a 10-stop route plan.")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    plans = route_plans_df()
    if plans.empty:
        st.info("No route plans uploaded yet.")
    else:
        p1, p2 = st.columns([1.2, 1])
        selected_day = p1.selectbox("Route date", ["All Days"] + sorted(plans["date"].unique().tolist(), reverse=True))
        selected_status = p2.selectbox("Status", ["All", "Pending", "In Route", "Completed"])

        filtered = plans.copy()
        if selected_day != "All Days":
            filtered = filtered[filtered["date"] == selected_day]
        if selected_status != "All":
            filtered = filtered[filtered["status"] == selected_status]
        filtered = filtered.sort_values(["date", "company"], ascending=[False, True])

        for dt in filtered["date"].drop_duplicates():
            day_df = filtered[filtered["date"] == dt]
            with st.expander(f"{dt} · {len(day_df)} planned stops", expanded=(selected_day != "All Days")):
                for _, row in day_df.iterrows():
                    c1, c2, c3 = st.columns([2.1, 1.05, 1])
                    c1.markdown(
                        f"**{row['company']}**  \n"
                        f"<span class='small-note'>{row.get('address', '')}</span>  \n"
                        f"<span class='small-note'>{row.get('cat', 'Other')} · {row.get('contact', '')}</span>",
                        unsafe_allow_html=True,
                    )
                    new_status = c2.selectbox(
                        "Status",
                        ["Pending", "In Route", "Completed"],
                        index=["Pending", "In Route", "Completed"].index(row["status"]),
                        key=f"status_{row['upload_id']}",
                    )
                    if new_status != row["status"]:
                        for plan in st.session_state.route_uploads:
                            if plan["upload_id"] == row["upload_id"]:
                                plan["status"] = new_status
                        st.rerun()
                    c3.markdown(
                        f"<div style='margin-top:1.9rem;background:{STATUS_COLOR.get(row['status'], '#999')};color:white;padding:0.42rem 0.65rem;border-radius:999px;text-align:center'>{row['status']}</div>",
                        unsafe_allow_html=True,
                    )

# ── Bean Tracker ──────────────────────────────────────────────────────
elif page == "🫘 Bean Tracker":
    df = stops_df()
    st.markdown(
        """
        <div class='hero'>
          <h1>Bean Tracker</h1>
          <p>Total bags always match total stops. Whole bean is based on what you explicitly logged. Ground coffee is automatically treated as the remaining bags that were not marked whole bean.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3 = st.columns(3)
    with m1: render_kpi("Total Stops", total_stops_count())
    with m2: render_kpi("Whole Bean", total_whole_bean())
    with m3: render_kpi("Ground Coffee", total_ground_coffee())

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Whole Bean Adjustments")
        if st.button("➕ Add 1 Whole Bean", key="wb_plus_unique", use_container_width=True):
            st.session_state.wb_adj += 1
            st.rerun()
        if st.button("➖ Remove 1 Whole Bean", key="wb_minus_unique", use_container_width=True):
            st.session_state.wb_adj -= 1
            st.rerun()
        st.caption(f"Logged whole bean from stops: {int(df['wb'].sum()) if not df.empty else 0}")
        st.caption(f"Manual adjustment: {st.session_state.wb_adj:+d}")
        st.caption(f"Total whole bean: {total_whole_bean()}")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Ground Coffee Adjustments")
        if st.button("➕ Add 1 Ground Coffee", key="gc_plus_unique", use_container_width=True):
            st.session_state.gc_adj += 1
            st.rerun()
        if st.button("➖ Remove 1 Ground Coffee", key="gc_minus_unique", use_container_width=True):
            st.session_state.gc_adj -= 1
            st.rerun()
        st.caption(f"Inferred ground from remaining stops: {max(len(df) - int(df['wb'].sum()), 0) if not df.empty else 0}")
        st.caption(f"Manual adjustment: {st.session_state.gc_adj:+d}")
        st.caption(f"Total ground coffee: {total_ground_coffee()}")
        st.markdown("</div>", unsafe_allow_html=True)

    perf = route_performance_df()
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Bags Given by Route Day")
    if not perf.empty:
        bean_df = perf[["Date", "WB", "Ground", "Stops"]].rename(columns={"WB": "Whole Bean", "Ground": "Ground Coffee", "Stops": "Total Bags"})
        st.dataframe(bean_df, use_container_width=True, hide_index=True)
        bar = go.Figure()
        bar.add_trace(go.Bar(name="Whole Bean", x=bean_df["Date"], y=bean_df["Whole Bean"], marker_color=STAR_COLOR[2]))
        bar.add_trace(go.Bar(name="Ground Coffee", x=bean_df["Date"], y=bean_df["Ground Coffee"], marker_color=STAR_COLOR[1]))
        bar.update_layout(
            barmode="group",
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(bar, use_container_width=True)
    else:
        st.info("No bean tracking data yet.")
    st.markdown("</div>", unsafe_allow_html=True)
