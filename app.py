import streamlit as st
import pandas as pd
import json
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import uuid

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Plexus Coffee Tracker",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Load seed data ────────────────────────────────────────────────────
@st.cache_data
def load_seed():
    with open("data.json") as f:
        return json.load(f)

# ── Session state init ────────────────────────────────────────────────
if "stops" not in st.session_state:
    seed = load_seed()
    st.session_state.stops   = seed["stops"]
    st.session_state.routes  = seed["routes"]
    st.session_state.wb_adj  = seed["beans"]["wb_adj"]
    st.session_state.gc_adj  = seed["beans"]["gc_adj"]

# ── Helpers ───────────────────────────────────────────────────────────
STAR_COLOR = {3: "#15803D", 2: "#C2410C", 1: "#B45309", 0: "#9CA3AF"}
STAR_BG    = {3: "#DCFCE7", 2: "#FFF7ED", 1: "#FEF3C7", 0: "#F3F4F6"}
STAR_LABEL = {3: "⭐⭐⭐", 2: "⭐⭐", 1: "⭐", 0: "—"}
CATEGORIES = ["Law", "Architecture", "Construction", "Biotech", "Finance",
              "Healthcare", "Real Estate", "Other"]

def stops_df():
    return pd.DataFrame(st.session_state.stops)

def total_wb():
    return sum(s["wb"] for s in st.session_state.stops) + st.session_state.wb_adj

def total_gc():
    return sum(s["gc"] for s in st.session_state.stops) + st.session_state.gc_adj

# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/emoji/96/hot-beverage.png", width=52)
    st.markdown("## Coffee Tracker\n**Plexus Technology**")
    st.divider()

    page = st.radio(
        "Navigate",
        ["📊 Overview", "📍 Map", "📋 Stop Log", "➕ Add Stop", "🫘 Bean Tracker"],
        label_visibility="collapsed"
    )

    st.divider()
    st.markdown(f"**☕ {total_wb()} WB &nbsp; 🫘 {total_gc()} GC**")
    st.caption(f"{len(st.session_state.stops)} stops · {len(st.session_state.routes)} routes")

    st.divider()
    # Export
    export_data = {
        "stops":  st.session_state.stops,
        "routes": st.session_state.routes,
        "beans":  {"wb_adj": st.session_state.wb_adj, "gc_adj": st.session_state.gc_adj}
    }
    st.download_button(
        "⬇ Export data (JSON)",
        data=json.dumps(export_data, indent=2),
        file_name="coffee_tracker_data.json",
        mime="application/json",
        use_container_width=True
    )

    # Import
    uploaded = st.file_uploader("⬆ Import data (JSON)", type="json", label_visibility="collapsed")
    if uploaded:
        data = json.load(uploaded)
        st.session_state.stops  = data["stops"]
        st.session_state.routes = data["routes"]
        st.session_state.wb_adj = data["beans"]["wb_adj"]
        st.session_state.gc_adj = data["beans"]["gc_adj"]
        st.success("Data imported!")
        st.rerun()

# ══════════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ══════════════════════════════════════════════════════════════════════
if page == "📊 Overview":
    st.title("Good morning, Chandler ☕")
    df = stops_df()

    rated = df[df["stars"] > 0]
    avg   = rated["stars"].mean() if len(rated) else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Stops",       len(df))
    c2.metric("⭐⭐⭐ 3-Star Stops", len(df[df["stars"] == 3]))
    c3.metric("☕ Whole Bean Given", total_wb(), help="From stops + manual adjustment")
    c4.metric("🫘 Ground Coffee Given", total_gc(), help="From stops + manual adjustment")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("⭐⭐ 2-Star Stops", len(df[df["stars"] == 2]))
    c6.metric("⭐ 1-Star Stops",  len(df[df["stars"] == 1]))
    c7.metric("Avg Rating",       f"{avg:.2f} / 3.0")
    c8.metric("Route Days",       len(st.session_state.routes))

    st.divider()

    col_l, col_r = st.columns(2)

    # Star distribution bar chart
    with col_l:
        st.subheader("Star Distribution")
        star_data = pd.DataFrame([
            {"Rating": "⭐ 1 Star",   "Count": len(df[df["stars"] == 1]), "color": "#B45309"},
            {"Rating": "⭐⭐ 2 Stars", "Count": len(df[df["stars"] == 2]), "color": "#C2410C"},
            {"Rating": "⭐⭐⭐ 3 Stars","Count": len(df[df["stars"] == 3]), "color": "#15803D"},
        ])
        fig = px.bar(star_data, x="Rating", y="Count", color="Rating",
                     color_discrete_map={
                         "⭐ 1 Star": "#B45309",
                         "⭐⭐ 2 Stars": "#C2410C",
                         "⭐⭐⭐ 3 Stars": "#15803D"
                     }, text="Count")
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, height=320,
                          plot_bgcolor="rgba(0,0,0,0)",
                          paper_bgcolor="rgba(0,0,0,0)",
                          yaxis=dict(showgrid=True, gridcolor="#F0E6D3"))
        st.plotly_chart(fig, use_container_width=True)

    # Avg rating by route day
    with col_r:
        st.subheader("Avg Rating by Route Day")
        trend = []
        for r in st.session_state.routes:
            rs = [s for s in st.session_state.stops if s["route_id"] == r["id"] and s["stars"] > 0]
            if rs:
                trend.append({"Date": r["date"][5:], "Avg": round(sum(s["stars"] for s in rs) / len(rs), 2)})
        if trend:
            tdf = pd.DataFrame(trend)
            fig2 = px.line(tdf, x="Date", y="Avg", markers=True,
                           color_discrete_sequence=["#C17F3B"])
            fig2.update_traces(line_width=2.5, marker_size=8)
            fig2.update_layout(height=320, yaxis=dict(range=[0, 3.2], gridcolor="#F0E6D3"),
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

    # Industry breakdown
    st.subheader("Avg Rating by Industry")
    if len(rated):
        by_cat = rated.groupby("cat").agg(
            Stops=("stars", "count"),
            Avg=("stars", "mean"),
            Stars3=("stars", lambda x: (x == 3).sum())
        ).reset_index().sort_values("Avg", ascending=False)
        by_cat["Avg"] = by_cat["Avg"].round(2)
        by_cat.columns = ["Industry", "Stops", "Avg Rating", "3-Star Stops"]
        st.dataframe(by_cat, use_container_width=True, hide_index=True)

    # Recent stops
    st.subheader("Recent Stops")
    recent = sorted(st.session_state.stops, key=lambda x: x["date"], reverse=True)[:8]
    for s in recent:
        col_a, col_b, col_c = st.columns([3, 1, 4])
        col_a.markdown(f"**{s['company']}**  \n<small>{s['date']} · {s['cat']}</small>",
                       unsafe_allow_html=True)
        col_b.markdown(STAR_LABEL.get(s["stars"], "—"))
        col_c.markdown(f"<small>{s['notes']}</small>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
# PAGE: MAP
# ══════════════════════════════════════════════════════════════════════
elif page == "📍 Map":
    st.title("Route Map")
    df = stops_df()
    mapped = df[df["lat"].notna() & df["lng"].notna()]
    st.caption(f"{len(mapped)} stops plotted across the Phoenix metro")

    # Filters
    fc1, fc2 = st.columns(2)
    star_filter = fc1.multiselect("Filter by stars", [3, 2, 1],
                                  default=[3, 2, 1],
                                  format_func=lambda x: STAR_LABEL[x])
    cat_filter  = fc2.multiselect("Filter by industry", sorted(df["cat"].unique()),
                                  default=list(df["cat"].unique()))

    filtered = mapped[mapped["stars"].isin(star_filter) & mapped["cat"].isin(cat_filter)]

    # Build map
    m = folium.Map(location=[33.480, -111.980], zoom_start=11,
                   tiles="CartoDB positron")

    for _, s in filtered.iterrows():
        col   = STAR_COLOR.get(int(s["stars"]), "#9CA3AF")
        stars = STAR_LABEL.get(int(s["stars"]), "—")
        popup_html = f"""
        <div style='font-family:sans-serif;min-width:200px'>
          <b style='font-size:14px'>{s['company']}</b><br>
          <span style='color:#6B3D2E;font-size:12px'>{s['date']} · {s['cat']}</span><br>
          <span style='font-size:18px'>{stars}</span><br>
          {'<br><small>' + str(s['notes']) + '</small>' if s['notes'] else ''}
          <br><small>WB: {int(s['wb'])} &nbsp; GC: {int(s['gc'])}</small>
        </div>"""
        folium.CircleMarker(
            location=[s["lat"], s["lng"]],
            radius=11,
            color="white", weight=2.5,
            fill=True, fill_color=col, fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=240),
            tooltip=s["company"]
        ).add_to(m)

    st_folium(m, width=None, height=600, returned_objects=[])

    # Legend
    lc1, lc2, lc3 = st.columns(3)
    lc1.markdown("🟢 **3 Stars** — Highly engaged")
    lc2.markdown("🟠 **2 Stars** — Good visit")
    lc3.markdown("🟡 **1 Star** — Low engagement")

# ══════════════════════════════════════════════════════════════════════
# PAGE: STOP LOG
# ══════════════════════════════════════════════════════════════════════
elif page == "📋 Stop Log":
    st.title("Stop Log")
    df = stops_df()

    sc1, sc2, sc3 = st.columns(3)
    search      = sc1.text_input("Search", placeholder="Company name, notes...")
    star_filter = sc2.selectbox("Stars", ["All", "⭐⭐⭐ 3 Stars", "⭐⭐ 2 Stars", "⭐ 1 Star"])
    cat_filter  = sc3.selectbox("Industry", ["All"] + sorted(df["cat"].unique().tolist()))

    filtered = df.copy()
    if search:
        mask = (filtered["company"].str.contains(search, case=False, na=False) |
                filtered["notes"].str.contains(search, case=False, na=False))
        filtered = filtered[mask]
    if star_filter != "All":
        n = int(star_filter[0])
        filtered = filtered[filtered["stars"] == n]
    if cat_filter != "All":
        filtered = filtered[filtered["cat"] == cat_filter]

    filtered = filtered.sort_values("date", ascending=False)
    st.caption(f"{len(filtered)} stops")

    # Display grouped by date
    for dt in filtered["date"].unique():
        day_df = filtered[filtered["date"] == dt].sort_values("stop")
        route  = next((r for r in st.session_state.routes if r["date"] == dt), None)
        label  = f"**{dt}**" + (f"  —  {route['name']}" if route else "")

        with st.expander(f"{dt}  ·  {route['name'] if route else ''}  ·  {len(day_df)} stops"):
            for _, s in day_df.iterrows():
                c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 3])
                c1.markdown(f"**{s['company']}**  \n<small>{s['cat']}</small>",
                            unsafe_allow_html=True)
                c2.markdown(STAR_LABEL.get(int(s["stars"]), "—"))
                c3.markdown(f"☕ {int(s['wb'])}" if s["wb"] else "—")
                c4.markdown(f"🫘 {int(s['gc'])}" if s["gc"] else "—")
                c5.markdown(f"<small>{s['notes']}</small>", unsafe_allow_html=True)

    # Full table toggle
    if st.checkbox("Show full table"):
        display = filtered[["date", "company", "cat", "stars", "wb", "gc", "notes"]].copy()
        display.columns = ["Date", "Company", "Industry", "Stars", "WB", "GC", "Notes"]
        st.dataframe(display, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════
# PAGE: ADD STOP
# ══════════════════════════════════════════════════════════════════════
elif page == "➕ Add Stop":
    st.title("Log a Stop")

    col_form, col_today = st.columns([2, 1])

    with col_form:
        with st.form("add_stop_form", clear_on_submit=True):
            st.subheader("Stop Details")

            route_date = st.date_input("Date", value=date.today())
            date_str   = route_date.strftime("%Y-%m-%d")

            existing_route = next(
                (r for r in st.session_state.routes if r["date"] == date_str), None
            )
            if existing_route:
                st.info(f"Adding to: **{existing_route['name']}**")
            else:
                new_route_name = st.text_input("Route name (new)", placeholder="e.g. Phoenix Law Week 4")

            company = st.text_input("Company Name *")
            cat     = st.selectbox("Industry", CATEGORIES)
            address = st.text_input("Address", placeholder="1234 N Central Ave, Phoenix AZ")
            contact = st.text_input("Contact Name")

            st.subheader("Rating")
            stars = st.radio("Star Rating", [1, 2, 3],
                             format_func=lambda x: STAR_LABEL[x],
                             horizontal=True)

            st.subheader("Coffee Left")
            wc1, wc2 = st.columns(2)
            wb = wc1.number_input("Whole Bean bags", min_value=0, max_value=20, value=0, step=1)
            gc = wc2.number_input("Ground Coffee bags", min_value=0, max_value=20, value=0, step=1)

            notes   = st.text_area("Notes", placeholder="What happened? Any key details...")
            submit  = st.form_submit_button("✅ Save Stop", use_container_width=True)

        if submit and company:
            route_id = existing_route["id"] if existing_route else f"r-{uuid.uuid4().hex[:8]}"
            if not existing_route:
                name = new_route_name if new_route_name else f"Route {date_str}"
                st.session_state.routes.append({"id": route_id, "date": date_str, "name": name})

            stops_today = [s for s in st.session_state.stops if s["date"] == date_str]
            st.session_state.stops.append({
                "id":       f"s-{uuid.uuid4().hex[:8]}",
                "route_id": route_id,
                "date":     date_str,
                "stop":     len(stops_today) + 1,
                "company":  company,
                "cat":      cat,
                "lat":      None,
                "lng":      None,
                "stars":    stars,
                "wb":       wb,
                "gc":       gc,
                "notes":    notes
            })
            st.success(f"✅ Saved: **{company}** — {STAR_LABEL[stars]}")
            st.rerun()
        elif submit:
            st.warning("Company name is required.")

    with col_today:
        date_str_today = date.today().strftime("%Y-%m-%d")
        today_stops = [s for s in st.session_state.stops if s["date"] == date_str_today]
        st.subheader(f"Today ({date_str_today})")
        if not today_stops:
            st.caption("No stops logged yet today.")
        else:
            for s in today_stops:
                st.markdown(f"**{s['stop']}.** {s['company']}  \n{STAR_LABEL.get(s['stars'], '—')}")
            st.divider()
            st.markdown(f"**WB today:** {sum(s['wb'] for s in today_stops)}")
            st.markdown(f"**GC today:** {sum(s['gc'] for s in today_stops)}")

# ══════════════════════════════════════════════════════════════════════
# PAGE: BEAN TRACKER
# ══════════════════════════════════════════════════════════════════════
elif page == "🫘 Bean Tracker":
    st.title("Bean Tracker")
    st.caption("Your running count of coffee samples given out. Adjust manually anytime.")

    from_stops_wb = sum(s["wb"] for s in st.session_state.stops)
    from_stops_gc = sum(s["gc"] for s in st.session_state.stops)

    col1, col2 = st.columns(2)

    # Whole Bean
    with col1:
        st.subheader("☕ Whole Bean")
        st.metric("Total Given", total_wb(), help="From stop logs + manual adjustment")

        bc1, bc2, bc3 = st.columns([1, 1, 1])
        if bc1.button("➕ Add 1", key="wb_plus", use_container_width=True):
            st.session_state.wb_adj += 1
            st.rerun()
        bc2.markdown(f"<div style='text-align:center;padding-top:8px;font-size:20px;font-weight:700'>{st.session_state.wb_adj:+d}</div>", unsafe_allow_html=True)
        if bc3.button("➖ Remove 1", key="wb_minus", use_container_width=True):
            st.session_state.wb_adj -= 1
            st.rerun()

        st.divider()
        st.caption(f"From stop logs: **{from_stops_wb}** bags")
        st.caption(f"Manual adjustment: **{st.session_state.wb_adj:+d}**")
        st.caption(f"**Total: {total_wb()} bags**")

    # Ground Coffee
    with col2:
        st.subheader("🫘 Ground Coffee")
        st.metric("Total Given", total_gc(), help="From stop logs + manual adjustment")

        gc1, gc2, gc3 = st.columns([1, 1, 1])
        if gc1.button("➕ Add 1", key="gc_plus", use_container_width=True):
            st.session_state.gc_adj += 1
            st.rerun()
        gc2.markdown(f"<div style='text-align:center;padding-top:8px;font-size:20px;font-weight:700'>{st.session_state.gc_adj:+d}</div>", unsafe_allow_html=True)
        if gc3.button("➖ Remove 1", key="gc_minus", use_container_width=True):
            st.session_state.gc_adj -= 1
            st.rerun()

        st.divider()
        st.caption(f"From stop logs: **{from_stops_gc}** bags")
        st.caption(f"Manual adjustment: **{st.session_state.gc_adj:+d}**")
        st.caption(f"**Total: {total_gc()} bags**")

    # By route day
    st.divider()
    st.subheader("Bags Given by Route Day")
    rows = []
    for dt in sorted(set(s["date"] for s in st.session_state.stops), reverse=True):
        day = [s for s in st.session_state.stops if s["date"] == dt]
        wb  = sum(s["wb"] for s in day)
        gc  = sum(s["gc"] for s in day)
        if wb or gc:
            rows.append({"Date": dt, "Whole Bean ☕": wb, "Ground Coffee 🫘": gc, "Total": wb + gc})
    if rows:
        rdf = pd.DataFrame(rows)
        st.dataframe(rdf, use_container_width=True, hide_index=True)

        fig = px.bar(rdf, x="Date", y=["Whole Bean ☕", "Ground Coffee 🫘"],
                     barmode="group",
                     color_discrete_map={"Whole Bean ☕": "#C17F3B", "Ground Coffee 🫘": "#6B3D2E"})
        fig.update_layout(height=300, plot_bgcolor="rgba(0,0,0,0)",
                          paper_bgcolor="rgba(0,0,0,0)",
                          yaxis=dict(gridcolor="#F0E6D3"), legend_title="")
        st.plotly_chart(fig, use_container_width=True)

    # Save reminder
    st.divider()
    st.info("💾 **To save your data permanently:** use the **Export data** button in the sidebar, then upload that JSON file back anytime to restore your counts.")
