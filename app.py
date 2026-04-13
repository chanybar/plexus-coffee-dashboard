import streamlit as st
import pandas as pd
import json
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import uuid

# NOTE: Dashboard updated 2026-04-13
# - Satellite map view
# - Route-day filtering on map and stop log
# - KPI overview simplified for ops reporting

# ── Page config ───────────────────────────────────────────────────────
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

if "stops" not in st.session_state:
    seed = load_seed()
    st.session_state.stops = seed["stops"]
    st.session_state.routes = seed["routes"]
    st.session_state.wb_adj = seed["beans"]["wb_adj"]
    st.session_state.gc_adj = seed["beans"]["gc_adj"]

STAR_COLOR = {3: "#15803D", 2: "#C2410C", 1: "#B45309", 0: "#9CA3AF"}
STAR_LABEL = {3: "⭐⭐⭐", 2: "⭐⭐", 1: "⭐", 0: "—"}
CATEGORIES = ["Law", "Architecture", "Construction", "Biotech", "Finance", "Healthcare", "Real Estate", "Other"]

def stops_df():
    return pd.DataFrame(st.session_state.stops)

def total_wb():
    return sum(s["wb"] for s in st.session_state.stops) + st.session_state.wb_adj

def total_gc():
    return sum(s["gc"] for s in st.session_state.stops) + st.session_state.gc_adj

with st.sidebar:
    page = st.radio("Navigate", ["📊 Overview", "📍 Map", "📋 Stop Log", "➕ Add Stop"])

if page == "📊 Overview":
    st.title("Plexus Coffee Analytics ☕")
    df = stops_df()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Stops", len(df))
    c2.metric("3-Star", len(df[df["stars"] == 3]))
    c3.metric("2-Star", len(df[df["stars"] == 2]))
    c4.metric("1-Star", len(df[df["stars"] == 1]))
    c5.metric("Bags Given", total_wb() + total_gc())
    st.metric("Whole Bean", total_wb())
    st.metric("Ground Coffee", total_gc())

elif page == "📍 Map":
    st.title("Satellite Route Map")
    df = stops_df()
    route_options = ["All Days"] + [r["date"] for r in st.session_state.routes]
    selected_day = st.selectbox("View route day", route_options)
    mapped = df[df["lat"].notna() & df["lng"].notna()]
    if selected_day != "All Days":
        mapped = mapped[mapped["date"] == selected_day]

    m = folium.Map(location=[33.480, -111.980], zoom_start=11, tiles=None)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Satellite",
        overlay=False,
        control=True,
    ).add_to(m)

    for _, s in mapped.iterrows():
        folium.CircleMarker(
            location=[s["lat"], s["lng"]],
            radius=10,
            color="white",
            weight=2,
            fill=True,
            fill_color=STAR_COLOR.get(int(s["stars"]), "#9CA3AF"),
            fill_opacity=0.9,
            tooltip=f"{s['company']} · {s['date']}"
        ).add_to(m)

    st_folium(m, width=None, height=600)

elif page == "📋 Stop Log":
    st.title("Daily Stop Log")
    df = stops_df().sort_values("date", ascending=False)
    route_options = ["All Days"] + sorted(df["date"].unique().tolist(), reverse=True)
    selected_day = st.selectbox("Filter by day", route_options)
    if selected_day != "All Days":
        df = df[df["date"] == selected_day]
    st.dataframe(df[["date", "company", "cat", "stars", "wb", "gc", "notes"]], use_container_width=True)

elif page == "➕ Add Stop":
    st.title("Log a Stop")
    st.info("New stops will appear on the map when latitude and longitude are available in the saved data.")
