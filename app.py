import streamlit as st
import pandas as pd
import json
import folium
from streamlit_folium import st_folium
import plotly.express as px
from datetime import date
import uuid
from io import StringIO

st.set_page_config(
    page_title="Plexus Coffee Tracker",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_data
def load_seed():
    with open("data.json") as f:
        return json.load(f)

def init_state():
    if "stops" not in st.session_state:
        seed = load_seed()
        st.session_state.stops = seed["stops"]
        st.session_state.routes = seed["routes"]
        st.session_state.wb_adj = seed["beans"]["wb_adj"]
        st.session_state.gc_adj = seed["beans"]["gc_adj"]
    if "route_uploads" not in st.session_state:
        st.session_state.route_uploads = []
    if "route_upload_counter" not in st.session_state:
        st.session_state.route_upload_counter = 0

init_state()

STAR_COLOR = {3: "#2F6B4F", 2: "#B87333", 1: "#8B5E3C", 0: "#B6AAA0"}
STAR_LABEL = {3: "⭐⭐⭐", 2: "⭐⭐", 1: "⭐", 0: "—"}
CATEGORIES = ["Law", "Architecture", "Construction", "Biotech", "Finance", "Healthcare", "Real Estate", "Other"]

def stops_df():
    df = pd.DataFrame(st.session_state.stops)
    if df.empty:
        return pd.DataFrame(columns=["id","route_id","date","stop","company","cat","lat","lng","stars","wb","gc","notes","address","contact","source_upload_id","route_status"])
    for col in ["address", "contact", "source_upload_id", "route_status"]:
        if col not in df.columns:
            df[col] = ""
    return df

def route_uploads_df():
    df = pd.DataFrame(st.session_state.route_uploads)
    if df.empty:
        return pd.DataFrame(columns=["upload_id","date","company","address","cat","contact","notes","status"])
    return df

def total_wb():
    return int(sum(s.get("wb", 0) for s in st.session_state.stops) + st.session_state.wb_adj)

def total_gc():
    return int(sum(s.get("gc", 0) for s in st.session_state.stops) + st.session_state.gc_adj)

def total_bags():
    return total_wb() + total_gc()

def get_route_name(route_id, route_date):
    route = next((r for r in st.session_state.routes if r["id"] == route_id), None)
    if route:
        return route["name"]
    fallback = next((r for r in st.session_state.routes if r["date"] == route_date), None)
    return fallback["name"] if fallback else f"Route {route_date}"

def ensure_route_for_date(date_str, preferred_name=None):
    existing = next((r for r in st.session_state.routes if r["date"] == date_str), None)
    if existing:
        return existing["id"]
    new_id = f"r-{uuid.uuid4().hex[:8]}"
    st.session_state.routes.append({
        "id": new_id,
        "date": date_str,
        "name": preferred_name or f"Route {date_str}"
    })
    return new_id

def status_chip(value):
    mapping = {
        "Pending": "#F7E7CE",
        "In Route": "#E8DCCB",
        "Completed": "#DDEEDF"
    }
    return mapping.get(value, "#F3EEE8")

st.markdown("""
<style>
:root{
  --bg:#f5efe6;
  --paper:#fbf7f2;
  --card:#f8f1e7;
  --ink:#2d2218;
  --muted:#7a6858;
  --line:#e8dccd;
  --accent:#6f4e37;
  --accent-2:#b87333;
  --green:#2f6b4f;
}
.stApp{
  background: linear-gradient(180deg, #f6efe6 0%, #f3ebdf 100%);
  color: var(--ink);
}
section[data-testid="stSidebar"]{
  background: #efe5d8;
  border-right: 1px solid var(--line);
}
h1,h2,h3{
  color: var(--ink);
  letter-spacing:-0.02em;
}
.block-container{
  padding-top: 2rem;
  padding-bottom: 3rem;
}
.hero{
  background: linear-gradient(120deg, rgba(111,78,55,0.96) 0%, rgba(184,115,51,0.94) 100%);
  color: #fffaf5;
  padding: 1.6rem 1.8rem;
  border-radius: 22px;
  box-shadow: 0 12px 40px rgba(111,78,55,0.16);
  margin-bottom: 1rem;
}
.hero h1{
  color:#fffaf5 !important;
  margin:0;
  font-size:2.2rem;
}
.hero p{
  margin:0.45rem 0 0 0;
  color:#f7ebdd;
  font-size:1rem;
}
.kpi-card{
  background: rgba(251,247,242,0.96);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 1rem 1.05rem;
  box-shadow: 0 10px 25px rgba(77,49,28,0.06);
}
.kpi-label{
  color: var(--muted);
  font-size: 0.86rem;
  margin-bottom: 0.2rem;
}
.kpi-value{
  color: var(--ink);
  font-size: 1.8rem;
  font-weight: 700;
}
.section-card{
  background: rgba(251,247,242,0.97);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 1rem 1rem 0.65rem 1rem;
  box-shadow: 0 10px 25px rgba(77,49,28,0.05);
  margin-bottom: 1rem;
}
.small-note{
  color: var(--muted);
  font-size: 0.92rem;
}
.route-pill{
  display:inline-block;
  background:#efe2d3;
  color:#5a4330;
  border:1px solid #e1d2c0;
  border-radius:999px;
  padding:0.28rem 0.6rem;
  font-size:0.82rem;
  margin-right:0.45rem;
  margin-top:0.25rem;
}
div[data-testid="stMetricValue"]{
  color: var(--ink);
}
div[data-testid="stMetricLabel"]{
  color: var(--muted);
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ☕ Plexus Coffee Tracker")
    st.caption("Adonai-inspired field dashboard")
    page = st.radio(
        "Navigate",
        ["📊 Overview", "🗺️ Map", "📋 Stop Log", "➕ Add Stop", "📝 Route Plans", "🫘 Bean Tracker"],
        label_visibility="collapsed"
    )
    st.divider()
    st.markdown(f"**Stops:** {len(st.session_state.stops)}")
    st.markdown(f"**Whole Bean:** {total_wb()}")
    st.markdown(f"**Ground:** {total_gc()}")
    st.markdown(f"**Bags Given:** {total_bags()}")

    export_data = {
        "stops": st.session_state.stops,
        "routes": st.session_state.routes,
        "beans": {"wb_adj": st.session_state.wb_adj, "gc_adj": st.session_state.gc_adj},
        "route_uploads": st.session_state.route_uploads
    }
    st.download_button(
        "⬇ Export Dashboard Data",
        data=json.dumps(export_data, indent=2),
        file_name="coffee_tracker_data.json",
        mime="application/json",
        use_container_width=True
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

df = stops_df()

if page == "📊 Overview":
    st.markdown("""
    <div class="hero">
      <h1>Plexus Coffee Overview</h1>
      <p>Brew hope, track outreach, and keep your daily route performance clean, visual, and easy to share.</p>
    </div>
    """, unsafe_allow_html=True)

    star_3 = int((df["stars"] == 3).sum()) if not df.empty else 0
    star_2 = int((df["stars"] == 2).sum()) if not df.empty else 0
    star_1 = int((df["stars"] == 1).sum()) if not df.empty else 0

    k1, k2, k3, k4 = st.columns(4)
    for col, label, value in [
        (k1, "Total Stops", len(df)),
        (k2, "Total Bags Given", total_bags()),
        (k3, "Whole Bean", total_wb()),
        (k4, "Ground Coffee", total_gc()),
    ]:
        with col:
            st.markdown(f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>', unsafe_allow_html=True)

    k5, k6, k7, k8 = st.columns(4)
    for col, label, value in [
        (k5, "3-Star Stops", star_3),
        (k6, "2-Star Stops", star_2),
        (k7, "1-Star Stops", star_1),
        (k8, "Route Days", len(st.session_state.routes)),
    ]:
        with col:
            st.markdown(f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>', unsafe_allow_html=True)

    st.write("")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Star Distribution")
        star_data = pd.DataFrame({
            "Rating": ["1 Star", "2 Stars", "3 Stars"],
            "Count": [star_1, star_2, star_3]
        })
        fig = px.bar(
            star_data, x="Rating", y="Count", text="Count",
            color="Rating",
            color_discrete_map={"1 Star": "#8B5E3C", "2 Stars": "#B87333", "3 Stars": "#2F6B4F"}
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            showlegend=False, height=320,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="#eadfce"),
            margin=dict(l=10, r=10, t=10, b=10)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Bags Given by Route Day")
        if not df.empty:
            day_counts = df.groupby("date", as_index=False).agg(
                whole_bean=("wb", "sum"),
                ground=("gc", "sum")
            ).sort_values("date")
            day_counts["total"] = day_counts["whole_bean"] + day_counts["ground"]
            fig2 = px.line(
                day_counts, x="date", y="total", markers=True,
                color_discrete_sequence=["#6f4e37"]
            )
            fig2.update_layout(
                height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(gridcolor="#eadfce"),
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="Date", yaxis_title="Bags"
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No stops logged yet.")
        st.markdown('</div>', unsafe_allow_html=True)

    c3, c4 = st.columns([1.15, 1])

    with c3:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Recent Stops")
        recent = df.sort_values(["date", "stop"], ascending=[False, True]).tail(8) if not df.empty else pd.DataFrame()
        recent = recent.sort_values(["date", "stop"], ascending=[False, True])
        if not recent.empty:
            for _, s in recent.iterrows():
                route_name = get_route_name(s["route_id"], s["date"])
                st.markdown(
                    f"**{s['company']}** · {STAR_LABEL.get(int(s['stars']), '—')}  \n"
                    f"<span class='small-note'>{s['date']} · {route_name} · {s['cat']}</span>  \n"
                    f"<span class='small-note'>{s.get('notes', '') or 'No notes added.'}</span>",
                    unsafe_allow_html=True
                )
                st.divider()
        else:
            st.info("No recent stops yet.")
        st.markdown('</div>', unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Industry Breakdown")
        if not df.empty:
            industry = df.groupby("cat", as_index=False).agg(
                stops=("company", "count"),
                star_3=("stars", lambda x: int((x == 3).sum())),
                whole_bean=("wb", "sum"),
                ground=("gc", "sum")
            ).sort_values("stops", ascending=False)
            industry["bags"] = industry["whole_bean"] + industry["ground"]
            st.dataframe(
                industry.rename(columns={
                    "cat": "Industry",
                    "stops": "Stops",
                    "star_3": "3-Star",
                    "bags": "Bags"
                })[["Industry", "Stops", "3-Star", "Bags"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Industry analytics will appear here as you log stops.")
        st.markdown('</div>', unsafe_allow_html=True)

elif page == "🗺️ Map":
    st.markdown("""
    <div class="hero">
      <h1>Route Map</h1>
      <p>Street view keeps the route practical. Only stops with map coordinates are plotted, but every stop can still be logged.</p>
    </div>
    """, unsafe_allow_html=True)

    mapped = df[df["lat"].notna() & df["lng"].notna()].copy() if not df.empty else pd.DataFrame()
    route_choices = ["All Days"] + sorted(df["date"].dropna().unique().tolist(), reverse=True) if not df.empty else ["All Days"]
    mc1, mc2, mc3 = st.columns([1.1, 1, 1])
    selected_day = mc1.selectbox("View route day", route_choices)
    star_filter = mc2.multiselect("Filter stars", [3, 2, 1], default=[3, 2, 1], format_func=lambda x: STAR_LABEL[x])
    cats = sorted(df["cat"].dropna().unique().tolist()) if not df.empty else []
    cat_filter = mc3.multiselect("Filter industry", cats, default=cats)

    if not mapped.empty:
        if selected_day != "All Days":
            mapped = mapped[mapped["date"] == selected_day]
        if cat_filter:
            mapped = mapped[mapped["cat"].isin(cat_filter)]
        mapped = mapped[mapped["stars"].isin(star_filter)]

        m = folium.Map(location=[33.480, -111.980], zoom_start=11, tiles="CartoDB positron")
        for _, s in mapped.iterrows():
            route_name = get_route_name(s["route_id"], s["date"])
            popup_html = f"""
            <div style='font-family:Inter,sans-serif;min-width:220px'>
              <b style='font-size:14px'>{s['company']}</b><br>
              <span style='font-size:12px;color:#6f4e37'>{s['date']} · {route_name}</span><br>
              <span style='font-size:13px'>{s['cat']} · {STAR_LABEL.get(int(s['stars']), '—')}</span><br>
              <small>WB: {int(s['wb'])} · GC: {int(s['gc'])}</small><br>
              <small>{s.get('notes', '') or 'No notes added.'}</small>
            </div>
            """
            folium.CircleMarker(
                location=[float(s["lat"]), float(s["lng"])],
                radius=10,
                color="white",
                weight=2.5,
                fill=True,
                fill_color=STAR_COLOR.get(int(s["stars"]), "#B6AAA0"),
                fill_opacity=0.92,
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=s["company"]
            ).add_to(m)
        st_folium(m, width=None, height=620, returned_objects=[])
        missing_count = len(df) - len(df[df["lat"].notna() & df["lng"].notna()]) if not df.empty else 0
        st.caption(f"{len(mapped)} plotted stops shown. {missing_count} logged stops do not have map coordinates yet, but they still stay in the dashboard.")
    else:
        st.info("No mapped stops yet. You can still use Add Stop and Route Plans without coordinates.")

elif page == "📋 Stop Log":
    st.markdown("""
    <div class="hero">
      <h1>Stop Log</h1>
      <p>Clean daily tracking with route names, notes, coffee counts, and better date alignment.</p>
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.info("No stops logged yet.")
    else:
        sc1, sc2, sc3, sc4 = st.columns([1.15, 1, 1, 1.2])
        all_dates = sorted(df["date"].dropna().unique().tolist(), reverse=True)
        selected_day = sc1.selectbox("Filter by day", ["All Days"] + all_dates)
        selected_star = sc2.selectbox("Stars", ["All", "3", "2", "1"])
        selected_cat = sc3.selectbox("Industry", ["All"] + sorted(df["cat"].dropna().unique().tolist()))
        search = sc4.text_input("Search", placeholder="Company or notes")

        filtered = df.copy()
        if selected_day != "All Days":
            filtered = filtered[filtered["date"] == selected_day]
        if selected_star != "All":
            filtered = filtered[filtered["stars"] == int(selected_star)]
        if selected_cat != "All":
            filtered = filtered[filtered["cat"] == selected_cat]
        if search:
            filtered = filtered[
                filtered["company"].str.contains(search, case=False, na=False) |
                filtered["notes"].str.contains(search, case=False, na=False) |
                filtered["address"].str.contains(search, case=False, na=False)
            ]

        filtered = filtered.sort_values(["date", "stop"], ascending=[False, True])
        st.caption(f"{len(filtered)} stops shown")

        for dt in filtered["date"].drop_duplicates():
            day_df = filtered[filtered["date"] == dt].copy()
            route_names = sorted(set(day_df.apply(lambda x: get_route_name(x["route_id"], x["date"]), axis=1).tolist()))
            with st.expander(f"{dt} · {len(day_df)} stops", expanded=(selected_day != "All Days")):
                if route_names:
                    st.markdown("".join([f"<span class='route-pill'>{name}</span>" for name in route_names]), unsafe_allow_html=True)
                display = day_df[["stop", "company", "cat", "stars", "wb", "gc", "address", "notes"]].copy()
                display["stars"] = display["stars"].map(lambda x: STAR_LABEL.get(int(x), "—"))
                display.columns = ["Stop #", "Company", "Industry", "Rating", "WB", "GC", "Address", "Notes"]
                st.dataframe(display, use_container_width=True, hide_index=True)

elif page == "➕ Add Stop":
    st.markdown("""
    <div class="hero">
      <h1>Log a Stop</h1>
      <p>Add a stop fast. Address is optional for mapping, not required for saving.</p>
    </div>
    """, unsafe_allow_html=True)

    uploads_df = route_uploads_df()
    col_form, col_today = st.columns([1.45, 1])

    with col_form:
        with st.form("add_stop_form", clear_on_submit=True):
            ad1, ad2 = st.columns(2)
            route_date = ad1.date_input("Date", value=date.today())
            date_str = route_date.strftime("%Y-%m-%d")
            existing_route = next((r for r in st.session_state.routes if r["date"] == date_str), None)
            route_name_input = ad2.text_input("Route name", value=existing_route["name"] if existing_route else "")

            pending_for_day = uploads_df[(uploads_df["date"] == date_str) & (uploads_df["status"] != "Completed")] if not uploads_df.empty else pd.DataFrame()
            planned_label_map = {"Manual entry": None}
            if not pending_for_day.empty:
                for _, row in pending_for_day.iterrows():
                    label = f"{row['company']} · {row.get('address', '')}"
                    planned_label_map[label] = row["upload_id"]
            planned_choice = st.selectbox("Planned stop", list(planned_label_map.keys()))

            selected_plan = None
            if planned_label_map[planned_choice] is not None:
                selected_plan = pending_for_day[pending_for_day["upload_id"] == planned_label_map[planned_choice]].iloc[0]

            company = st.text_input("Company Name *", value="" if selected_plan is None else str(selected_plan.get("company", "")))
            cat_default = CATEGORIES.index(selected_plan["cat"]) if selected_plan is not None and selected_plan.get("cat") in CATEGORIES else 0
            cat = st.selectbox("Industry", CATEGORIES, index=cat_default)
            address = st.text_input("Address", value="" if selected_plan is None else str(selected_plan.get("address", "")))
            contact = st.text_input("Contact Name", value="" if selected_plan is None else str(selected_plan.get("contact", "")))

            rt1, rt2, rt3 = st.columns(3)
            stars = rt1.radio("Rating", [1, 2, 3], format_func=lambda x: STAR_LABEL[x], horizontal=True)
            wb = rt2.number_input("Whole Bean", min_value=0, max_value=20, value=0, step=1)
            gc = rt3.number_input("Ground Coffee", min_value=0, max_value=20, value=0, step=1)

            route_status = st.selectbox("Route Status", ["Completed", "In Route", "Pending"], index=0)
            notes = st.text_area("Notes", value="" if selected_plan is None else str(selected_plan.get("notes", "")))
            submit = st.form_submit_button("✅ Save Stop", use_container_width=True)

        if submit:
            if not company.strip():
                st.warning("Company name is required.")
            else:
                route_id = ensure_route_for_date(date_str, route_name_input.strip() or None)
                stops_today = [s for s in st.session_state.stops if s["date"] == date_str]
                new_stop = {
                    "id": f"s-{uuid.uuid4().hex[:8]}",
                    "route_id": route_id,
                    "date": date_str,
                    "stop": len(stops_today) + 1,
                    "company": company.strip(),
                    "cat": cat,
                    "lat": None,
                    "lng": None,
                    "stars": int(stars),
                    "wb": int(wb),
                    "gc": int(gc),
                    "notes": notes.strip(),
                    "address": address.strip(),
                    "contact": contact.strip(),
                    "route_status": route_status,
                    "source_upload_id": "" if selected_plan is None else str(selected_plan["upload_id"])
                }
                st.session_state.stops.append(new_stop)

                if selected_plan is not None:
                    for item in st.session_state.route_uploads:
                        if item["upload_id"] == str(selected_plan["upload_id"]):
                            item["status"] = "Completed" if route_status == "Completed" else route_status

                st.success(f"Saved {company.strip()} to {date_str}.")
                st.rerun()

    with col_today:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Stops for selected day")
        today_df = df[df["date"] == date_str].sort_values("stop") if not df.empty else pd.DataFrame()
        if not today_df.empty:
            for _, s in today_df.iterrows():
                st.markdown(
                    f"**{int(s['stop'])}. {s['company']}**  \n"
                    f"<span class='small-note'>{STAR_LABEL.get(int(s['stars']), '—')} · WB {int(s['wb'])} · GC {int(s['gc'])}</span>",
                    unsafe_allow_html=True
                )
                st.divider()
            st.markdown(f"**WB total:** {int(today_df['wb'].sum())}")
            st.markdown(f"**GC total:** {int(today_df['gc'].sum())}")
        else:
            st.caption("No stops saved yet for this day.")
        st.markdown('</div>', unsafe_allow_html=True)

elif page == "📝 Route Plans":
    st.markdown("""
    <div class="hero">
      <h1>Route Plans</h1>
      <p>Your marketing lady can upload the day's route list here. You can track each stop as pending, in route, or completed.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Upload route list")
    st.caption("Use CSV with columns like: date, company, address, cat, contact, notes")
    upload = st.file_uploader("Upload route CSV", type=["csv"], key="route_csv_upload")
    if upload is not None:
        try:
            text = StringIO(upload.getvalue().decode("utf-8"))
            incoming = pd.read_csv(text)
            incoming.columns = [str(c).strip().lower() for c in incoming.columns]
            required = {"date", "company"}
            if not required.issubset(set(incoming.columns)):
                st.error("CSV needs at least 'date' and 'company' columns.")
            else:
                normalized = incoming.copy()
                for col in ["address", "cat", "contact", "notes"]:
                    if col not in normalized.columns:
                        normalized[col] = ""
                if "cat" in normalized.columns:
                    normalized["cat"] = normalized["cat"].apply(lambda x: x if x in CATEGORIES else "Other")
                normalized["date"] = pd.to_datetime(normalized["date"]).dt.strftime("%Y-%m-%d")
                if st.button("Add uploaded route list", type="primary", use_container_width=True):
                    added = 0
                    for _, row in normalized.iterrows():
                        st.session_state.route_upload_counter += 1
                        st.session_state.route_uploads.append({
                            "upload_id": f"u-{st.session_state.route_upload_counter}",
                            "date": row["date"],
                            "company": str(row.get("company", "")).strip(),
                            "address": str(row.get("address", "")).strip(),
                            "cat": str(row.get("cat", "Other")).strip() or "Other",
                            "contact": str(row.get("contact", "")).strip(),
                            "notes": str(row.get("notes", "")).strip(),
                            "status": "Pending"
                        })
                        ensure_route_for_date(row["date"])
                        added += 1
                    st.success(f"Added {added} planned stops.")
                    st.rerun()
                st.dataframe(normalized, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

    uploads_df = route_uploads_df()
    if uploads_df.empty:
        st.info("No route plans uploaded yet.")
    else:
        rp1, rp2 = st.columns([1.15, 1])
        dates = sorted(uploads_df["date"].dropna().unique().tolist(), reverse=True)
        selected_date = rp1.selectbox("Route date", ["All Days"] + dates)
        selected_status = rp2.selectbox("Status", ["All", "Pending", "In Route", "Completed"])

        plans = uploads_df.copy()
        if selected_date != "All Days":
            plans = plans[plans["date"] == selected_date]
        if selected_status != "All":
            plans = plans[plans["status"] == selected_status]
        plans = plans.sort_values(["date", "company"], ascending=[False, True])

        for dt in plans["date"].drop_duplicates():
            day_df = plans[plans["date"] == dt].copy()
            with st.expander(f"{dt} · {len(day_df)} planned stops", expanded=(selected_date != 'All Days')):
                for _, row in day_df.iterrows():
                    rc1, rc2, rc3 = st.columns([2.2, 1.05, 0.95])
                    rc1.markdown(
                        f"**{row['company']}**  \n"
                        f"<span class='small-note'>{row.get('address', '')}</span>  \n"
                        f"<span class='small-note'>{row.get('cat', 'Other')} · {row.get('contact', '')}</span>",
                        unsafe_allow_html=True
                    )
                    new_status = rc2.selectbox(
                        "Status",
                        ["Pending", "In Route", "Completed"],
                        index=["Pending", "In Route", "Completed"].index(row["status"]),
                        key=f"status_{row['upload_id']}"
                    )
                    if new_status != row["status"]:
                        for item in st.session_state.route_uploads:
                            if item["upload_id"] == row["upload_id"]:
                                item["status"] = new_status
                        st.rerun()
                    rc3.markdown(
                        f"<div style='margin-top:1.9rem;background:{status_chip(row['status'])};padding:0.4rem 0.65rem;border-radius:999px;text-align:center;border:1px solid #e4d6c8'>{row['status']}</div>",
                        unsafe_allow_html=True
                    )

elif page == "🫘 Bean Tracker":
    st.markdown("""
    <div class="hero">
      <h1>Bean Tracker</h1>
      <p>Quick running totals for whole bean and ground coffee, with manual adjustments when needed.</p>
    </div>
    """, unsafe_allow_html=True)

    from_stops_wb = int(sum(s.get("wb", 0) for s in st.session_state.stops))
    from_stops_gc = int(sum(s.get("gc", 0) for s in st.session_state.stops))
    b1, b2 = st.columns(2)

    with b1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Whole Bean")
        st.metric("Total Given", total_wb())
        p1, p2 = st.columns(2)
        if p1.button("➕ Add 1", use_container_width=True):
            st.session_state.wb_adj += 1
            st.rerun()
        if p2.button("➖ Remove 1", use_container_width=True):
            st.session_state.wb_adj -= 1
            st.rerun()
        st.caption(f"From stop logs: {from_stops_wb}")
        st.caption(f"Manual adjustment: {st.session_state.wb_adj:+d}")
        st.markdown('</div>', unsafe_allow_html=True)

    with b2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Ground Coffee")
        st.metric("Total Given", total_gc())
        p3, p4 = st.columns(2)
        if p3.button("➕ Add 1", use_container_width=True):
            st.session_state.gc_adj += 1
            st.rerun()
        if p4.button("➖ Remove 1", use_container_width=True):
            st.session_state.gc_adj -= 1
            st.rerun()
        st.caption(f"From stop logs: {from_stops_gc}")
        st.caption(f"Manual adjustment: {st.session_state.gc_adj:+d}")
        st.markdown('</div>', unsafe_allow_html=True)
