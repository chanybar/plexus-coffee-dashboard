import streamlit as st
import pandas as pd
import json
import re
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
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
    st.session_state.stops      = seed["stops"]
    st.session_state.routes     = seed["routes"]
    st.session_state.wb_adj     = seed["beans"]["wb_adj"]
    st.session_state.gc_adj     = seed["beans"]["gc_adj"]
    st.session_state.raw_notes  = seed.get("raw_notes", [])

if "pending_parse" not in st.session_state:
    st.session_state.pending_parse = None   # {"raw": str, "parsed": dict}

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
    # Ground coffee is inferred: every stop gets either WB or GC.
    # Explicit gc fields override; otherwise gc = stops_without_wb.
    explicit_gc = sum(s["gc"] for s in st.session_state.stops)
    explicit_wb = sum(s["wb"] for s in st.session_state.stops)
    inferred_gc = max(len(st.session_state.stops) - explicit_wb, 0)
    # Use inferred if explicit gc is suspiciously low (less than inferred)
    gc_from_stops = inferred_gc if explicit_gc < inferred_gc else explicit_gc
    return gc_from_stops + st.session_state.gc_adj

# ── Smart Note Parsers ────────────────────────────────────────────────

def _has_ai_key():
    try:
        return bool(st.secrets.get("ANTHROPIC_API_KEY", ""))
    except Exception:
        return False

def parse_note_ai(text):
    """Use Claude Haiku to extract structured data from a free-form note."""
    try:
        import anthropic
        api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None
        client = anthropic.Anthropic(api_key=api_key)
        today_str = date.today().strftime("%Y-%m-%d")
        cats = ", ".join(CATEGORIES)
        prompt = f"""You are parsing a coffee route delivery note for a B2B sales driver.
Today's date is {today_str}.

Note: "{text}"

Return ONLY a valid JSON object with any of these fields that are clearly present in the note:
{{
  "company":  "business name",
  "cat":      "one of: {cats}",
  "date":     "YYYY-MM-DD",
  "wb":       0,
  "gc":       0,
  "stars":    1,
  "notes":    "cleaned notes",
  "contact":  "contact person name"
}}

Rules:
- wb = whole bean bags (look for numbers before 'whole bean', 'WB', 'wb')
- gc = ground coffee bags (look for numbers before 'ground', 'GC', 'gc')
- stars 3 = loved / very interested / enthusiastic / amazing / excited
- stars 2 = okay / decent / good / neutral / fine
- stars 1 = not interested / rejected / cold / busy / no thanks
- date: interpret 'today', 'yesterday', 'last Monday', etc. relative to {today_str}
- cat: infer from business name or context (law firm → Law, etc.)
- If a field isn't in the note, omit it from the JSON entirely
- Return ONLY the JSON object — no markdown fences, no explanation"""

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        # Strip markdown fences if present
        if "```" in raw:
            raw = re.sub(r"```[a-z]*", "", raw).replace("```", "").strip()
        return json.loads(raw)
    except Exception:
        return None


def parse_note_simple(text):
    """Keyword/regex fallback parser — no API key required."""
    result = {}
    t = text.lower()
    today = date.today()

    # ── Date ──
    if "yesterday" in t:
        result["date"] = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        result["date"] = today.strftime("%Y-%m-%d")

    # ── Bag counts ──
    wb_m = re.search(r"(\d+)\s*(?:whole[\s-]?bean|wb)\b", t)
    gc_m = re.search(r"(\d+)\s*(?:ground(?:\s*coffee)?|gc)\b", t)
    # plain "X bag(s)" with no qualifier = whole bean by default
    plain_m = re.search(r"(\d+)\s*bags?\b", t) if not wb_m and not gc_m else None
    if wb_m:
        result["wb"] = int(wb_m.group(1))
    if gc_m:
        result["gc"] = int(gc_m.group(1))
    if plain_m:
        result["wb"] = int(plain_m.group(1))

    # ── Star rating ──
    three_star = ["loved", "love it", "great", "excellent", "amazing",
                  "enthusiastic", "very interested", "excited", "fantastic"]
    two_star   = ["okay", "ok", "decent", "good", "fine", "neutral", "interested"]
    one_star   = ["not interested", "rejected", "cold", "busy", "no thanks",
                  "passed", "not ready", "closed"]
    if any(w in t for w in three_star):
        result["stars"] = 3
    elif any(w in t for w in one_star):
        result["stars"] = 1
    elif any(w in t for w in two_star):
        result["stars"] = 2

    # ── Industry ──
    industry_map = {
        "Law":          ["law", "legal", "attorney", "counsel", "firm"],
        "Architecture": ["architect", "architecture", "design firm"],
        "Construction": ["construction", "build", "contractor", "general contractor"],
        "Biotech":      ["biotech", "bio", "pharma", "life science", "laboratory"],
        "Finance":      ["finance", "financial", "investment", "bank", "capital"],
        "Healthcare":   ["health", "medical", "clinic", "hospital", "dental"],
        "Real Estate":  ["real estate", "realty", "property", "brokerage"],
    }
    for cat, keywords in industry_map.items():
        if any(k in t for k in keywords):
            result["cat"] = cat
            break

    # ── Notes — keep original text ──
    result["notes"] = text.strip()

    return result


def parse_note(text):
    """Returns (parsed_dict, source_label)."""
    if _has_ai_key():
        parsed = parse_note_ai(text)
        if parsed:
            # Merge defaults for missing required fields
            return parsed, "🤖 AI"
    parsed = parse_note_simple(text)
    return parsed, "🔍 Keyword"

# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/emoji/96/hot-beverage.png", width=52)
    st.markdown("## Coffee Tracker\n**Plexus Technology**")
    st.divider()

    page = st.radio(
        "Navigate",
        ["📊 Overview", "📍 Map", "📋 Stop Log", "➕ Add Stop",
         "🗒️ Quick Notes", "🫘 Bean Tracker"],
        label_visibility="collapsed"
    )

    st.divider()
    st.markdown(f"**☕ {total_wb()} WB &nbsp; 🫘 {total_gc()} GC**")
    st.caption(f"{len(st.session_state.stops)} stops · {len(st.session_state.routes)} routes")

    if st.session_state.raw_notes:
        st.caption(f"🗒️ {len(st.session_state.raw_notes)} saved notes")

    st.divider()
    # Export
    export_data = {
        "stops":     st.session_state.stops,
        "routes":    st.session_state.routes,
        "beans":     {"wb_adj": st.session_state.wb_adj, "gc_adj": st.session_state.gc_adj},
        "raw_notes": st.session_state.raw_notes,
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
        st.session_state.stops     = data["stops"]
        st.session_state.routes    = data["routes"]
        st.session_state.wb_adj    = data["beans"]["wb_adj"]
        st.session_state.gc_adj    = data["beans"]["gc_adj"]
        st.session_state.raw_notes = data.get("raw_notes", [])
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
    c1.metric("Total Stops",          len(df))
    c2.metric("⭐⭐⭐ 3-Star Stops",   len(df[df["stars"] == 3]))
    c3.metric("☕ Whole Bean Given",   total_wb(), help="From stops + manual adjustment")
    c4.metric("🫘 Ground Coffee Given",total_gc(), help="From stops + manual adjustment")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("⭐⭐ 2-Star Stops", len(df[df["stars"] == 2]))
    c6.metric("⭐ 1-Star Stops",  len(df[df["stars"] == 1]))
    c7.metric("Avg Rating",       f"{avg:.2f} / 3.0")
    c8.metric("Route Days",       len(st.session_state.routes))

    st.divider()

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Star Distribution")
        star_data = pd.DataFrame([
            {"Rating": "⭐ 1 Star",    "Count": len(df[df["stars"] == 1]), "color": "#B45309"},
            {"Rating": "⭐⭐ 2 Stars",  "Count": len(df[df["stars"] == 2]), "color": "#C2410C"},
            {"Rating": "⭐⭐⭐ 3 Stars", "Count": len(df[df["stars"] == 3]), "color": "#15803D"},
        ])
        fig = px.bar(star_data, x="Rating", y="Count", color="Rating",
                     color_discrete_map={
                         "⭐ 1 Star":    "#B45309",
                         "⭐⭐ 2 Stars":  "#C2410C",
                         "⭐⭐⭐ 3 Stars": "#15803D"
                     }, text="Count")
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, height=320,
                          plot_bgcolor="rgba(0,0,0,0)",
                          paper_bgcolor="rgba(0,0,0,0)",
                          yaxis=dict(showgrid=True, gridcolor="#F0E6D3"))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Avg Rating by Route Day")
        trend = []
        for r in st.session_state.routes:
            rs = [s for s in st.session_state.stops
                  if s["route_id"] == r["id"] and s["stars"] > 0]
            if rs:
                trend.append({
                    "Date": r["date"][5:],
                    "Avg":  round(sum(s["stars"] for s in rs) / len(rs), 2)
                })
        if trend:
            tdf = pd.DataFrame(trend)
            fig2 = px.line(tdf, x="Date", y="Avg", markers=True,
                           color_discrete_sequence=["#C17F3B"])
            fig2.update_traces(line_width=2.5, marker_size=8)
            fig2.update_layout(height=320,
                               yaxis=dict(range=[0, 3.2], gridcolor="#F0E6D3"),
                               plot_bgcolor="rgba(0,0,0,0)",
                               paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

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

    fc1, fc2 = st.columns(2)
    star_filter = fc1.multiselect("Filter by stars", [3, 2, 1],
                                  default=[3, 2, 1],
                                  format_func=lambda x: STAR_LABEL[x])
    cat_filter  = fc2.multiselect("Filter by industry", sorted(df["cat"].unique()),
                                  default=list(df["cat"].unique()))

    filtered = mapped[mapped["stars"].isin(star_filter) & mapped["cat"].isin(cat_filter)]

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

    for dt in filtered["date"].unique():
        day_df = filtered[filtered["date"] == dt].sort_values("stop")
        route  = next((r for r in st.session_state.routes if r["date"] == dt), None)

        with st.expander(f"{dt}  ·  {route['name'] if route else ''}  ·  {len(day_df)} stops"):
            for _, s in day_df.iterrows():
                c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 3])
                c1.markdown(f"**{s['company']}**  \n<small>{s['cat']}</small>",
                            unsafe_allow_html=True)
                c2.markdown(STAR_LABEL.get(int(s["stars"]), "—"))
                c3.markdown(f"☕ {int(s['wb'])}" if s["wb"] else "—")
                c4.markdown(f"🫘 {int(s['gc'])}" if s["gc"] else "—")
                c5.markdown(f"<small>{s['notes']}</small>", unsafe_allow_html=True)

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

            notes  = st.text_area("Notes", placeholder="What happened? Any key details...")
            submit = st.form_submit_button("✅ Save Stop", use_container_width=True)

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
# PAGE: QUICK NOTES
# ══════════════════════════════════════════════════════════════════════
elif page == "🗒️ Quick Notes":
    st.title("🗒️ Quick Notes")
    st.caption(
        "Dump any raw note here — names, bags, vibes, whatever you remember. "
        "The app will figure out what it means and turn it into a stop entry."
    )

    if _has_ai_key():
        st.success("🤖 AI parsing active — notes will be interpreted by Claude.")
    else:
        st.info(
            "🔍 Keyword parsing active. "
            "To enable AI parsing, add **ANTHROPIC_API_KEY** to your Streamlit secrets."
        )

    st.divider()

    # ── Step 1: Input ─────────────────────────────────────────────────
    if st.session_state.pending_parse is None:
        st.subheader("Drop your note")

        raw_text = st.text_area(
            "Note",
            height=140,
            placeholder=(
                "Examples:\n"
                "  • 'Stopped by Smith & Jones Law, left 2 whole bean bags, Karen loved it'\n"
                "  • 'Couldn't get in at Phoenix Biotech — try again next week'\n"
                "  • '3 ground coffee at Apex Construction yesterday, guy was okay'"
            ),
            label_visibility="collapsed"
        )

        col_parse, col_note_only = st.columns([1, 1])
        parse_btn     = col_parse.button("🔍 Parse & Preview", use_container_width=True,
                                         type="primary", disabled=not raw_text.strip())
        note_only_btn = col_note_only.button("💾 Save as Raw Note Only", use_container_width=True,
                                             disabled=not raw_text.strip())

        if parse_btn and raw_text.strip():
            with st.spinner("Parsing note…"):
                parsed, source = parse_note(raw_text.strip())
            st.session_state.pending_parse = {
                "raw":    raw_text.strip(),
                "parsed": parsed,
                "source": source,
            }
            st.rerun()

        if note_only_btn and raw_text.strip():
            st.session_state.raw_notes.append({
                "id":   f"n-{uuid.uuid4().hex[:8]}",
                "ts":   date.today().strftime("%Y-%m-%d"),
                "text": raw_text.strip(),
                "saved_as_stop": False,
            })
            st.success("✅ Raw note saved.")
            st.rerun()

    # ── Step 2: Review & confirm ──────────────────────────────────────
    else:
        pp = st.session_state.pending_parse
        source = pp.get("source", "🔍 Keyword")
        p      = pp["parsed"]

        st.subheader(f"Here's what I understood  {source}")
        _raw_escaped = pp['raw'].replace('<', '&lt;').replace('>', '&gt;')
        _note_html = (
            "<div style='background:#F0E6D3;border-radius:10px;padding:14px 18px;"
            "font-style:italic;color:#5a3e2b;margin-bottom:12px'>"
            f"&ldquo;{_raw_escaped}&rdquo;</div>"
        )
        st.markdown(_note_html, unsafe_allow_html=True)

        with st.form("confirm_note_form"):
            nc1, nc2 = st.columns(2)

            company = nc1.text_input("Company *",
                                     value=p.get("company", ""),
                                     placeholder="Business name")
            cat_default = p.get("cat", CATEGORIES[0])
            if cat_default not in CATEGORIES:
                cat_default = CATEGORIES[0]
            cat = nc2.selectbox("Industry", CATEGORIES,
                                index=CATEGORIES.index(cat_default))

            nd1, nd2 = st.columns(2)
            try:
                default_date = date.fromisoformat(p.get("date", date.today().isoformat()))
            except ValueError:
                default_date = date.today()
            stop_date = nd1.date_input("Date", value=default_date)
            contact   = nd2.text_input("Contact", value=p.get("contact", ""))

            star_default = p.get("stars", 2)
            if star_default not in [1, 2, 3]:
                star_default = 2
            stars = st.radio("Rating", [1, 2, 3],
                             index=[1, 2, 3].index(star_default),
                             format_func=lambda x: STAR_LABEL[x],
                             horizontal=True)

            nb1, nb2 = st.columns(2)
            wb = nb1.number_input("Whole Bean bags ☕",
                                  min_value=0, max_value=20,
                                  value=int(p.get("wb", 0)), step=1)
            gc = nb2.number_input("Ground Coffee bags 🫘",
                                  min_value=0, max_value=20,
                                  value=int(p.get("gc", 0)), step=1)

            notes = st.text_area("Notes", value=p.get("notes", pp["raw"]), height=100)

            btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])
            save_btn   = btn_col1.form_submit_button("✅ Save as Stop", use_container_width=True,
                                                     type="primary")
            raw_btn    = btn_col2.form_submit_button("💾 Raw Note Only", use_container_width=True)
            cancel_btn = btn_col3.form_submit_button("✖ Cancel", use_container_width=True)

        if save_btn:
            if not company.strip():
                st.warning("Company name is required to save as a stop.")
            else:
                date_str = stop_date.strftime("%Y-%m-%d")
                existing_route = next(
                    (r for r in st.session_state.routes if r["date"] == date_str), None
                )
                route_id = existing_route["id"] if existing_route else f"r-{uuid.uuid4().hex[:8]}"
                if not existing_route:
                    st.session_state.routes.append({
                        "id":   route_id,
                        "date": date_str,
                        "name": f"Route {date_str}"
                    })
                stops_on_day = [s for s in st.session_state.stops if s["date"] == date_str]
                st.session_state.stops.append({
                    "id":       f"s-{uuid.uuid4().hex[:8]}",
                    "route_id": route_id,
                    "date":     date_str,
                    "stop":     len(stops_on_day) + 1,
                    "company":  company.strip(),
                    "cat":      cat,
                    "lat":      None,
                    "lng":      None,
                    "stars":    stars,
                    "wb":       wb,
                    "gc":       gc,
                    "notes":    notes.strip(),
                })
                # Also save raw note for reference
                st.session_state.raw_notes.append({
                    "id":            f"n-{uuid.uuid4().hex[:8]}",
                    "ts":            date_str,
                    "text":          pp["raw"],
                    "saved_as_stop": True,
                    "company":       company.strip(),
                })
                st.session_state.pending_parse = None
                st.success(f"✅ Stop saved: **{company.strip()}** — {STAR_LABEL[stars]}")
                st.rerun()

        if raw_btn:
            st.session_state.raw_notes.append({
                "id":            f"n-{uuid.uuid4().hex[:8]}",
                "ts":            date.today().strftime("%Y-%m-%d"),
                "text":          pp["raw"],
                "saved_as_stop": False,
            })
            st.session_state.pending_parse = None
            st.success("💾 Raw note saved.")
            st.rerun()

        if cancel_btn:
            st.session_state.pending_parse = None
            st.rerun()

    # ── Notes History ─────────────────────────────────────────────────
    if st.session_state.raw_notes:
        st.divider()
        st.subheader(f"Note History  ({len(st.session_state.raw_notes)})")

        for n in reversed(st.session_state.raw_notes):
            badge = "🟢 Saved as stop" if n.get("saved_as_stop") else "📋 Raw note"
            company_tag = f" → **{n['company']}**" if n.get("company") else ""
            with st.expander(f"{n['ts']}  ·  {badge}{company_tag}"):
                st.markdown(
                    f"<div style='font-style:italic;color:#5a3e2b'>{n['text']}</div>",
                    unsafe_allow_html=True
                )

# ══════════════════════════════════════════════════════════════════════
# PAGE: BEAN TRACKER
# ══════════════════════════════════════════════════════════════════════
elif page == "🫘 Bean Tracker":
    st.title("Bean Tracker")
    st.caption("Your running count of coffee samples given out. Adjust manually anytime.")

    from_stops_wb = sum(s["wb"] for s in st.session_state.stops)
    from_stops_gc = sum(s["gc"] for s in st.session_state.stops)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("☕ Whole Bean")
        st.metric("Total Given", total_wb(), help="From stop logs + manual adjustment")

        bc1, bc2, bc3 = st.columns([1, 1, 1])
        if bc1.button("➕ Add 1", key="wb_plus", use_container_width=True):
            st.session_state.wb_adj += 1
            st.rerun()
        _wb_html = f"<div style='text-align:center;padding-top:8px;font-size:20px;font-weight:700'>{st.session_state.wb_adj:+d}</div>"
        bc2.markdown(_wb_html, unsafe_allow_html=True)
        if bc3.button("➖ Remove 1", key="wb_minus", use_container_width=True):
            st.session_state.wb_adj -= 1
            st.rerun()

        st.divider()
        st.caption(f"From stop logs: **{from_stops_wb}** bags")
        st.caption(f"Manual adjustment: **{st.session_state.wb_adj:+d}**")
        st.caption(f"**Total: {total_wb()} bags**")

    with col2:
        st.subheader("🫘 Ground Coffee")
        st.metric("Total Given", total_gc(), help="From stop logs + manual adjustment")

        gc1, gc2, gc3 = st.columns([1, 1, 1])
        if gc1.button("➕ Add 1", key="gc_plus", use_container_width=True):
            st.session_state.gc_adj += 1
            st.rerun()
        _gc_html = f"<div style='text-align:center;padding-top:8px;font-size:20px;font-weight:700'>{st.session_state.gc_adj:+d}</div>"
        gc2.markdown(_gc_html, unsafe_allow_html=True)
        if gc3.button("➖ Remove 1", key="gc_minus", use_container_width=True):
            st.session_state.gc_adj -= 1
            st.rerun()

        st.divider()
        st.caption(f"From stop logs: **{from_stops_gc}** bags")
        st.caption(f"Manual adjustment: **{st.session_state.gc_adj:+d}**")
        st.caption(f"**Total: {total_gc()} bags**")

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
                     color_discrete_map={
                         "Whole Bean ☕":    "#C17F3B",
                         "Ground Coffee 🫘": "#6B3D2E"
                     })
        fig.update_layout(height=300, plot_bgcolor="rgba(0,0,0,0)",
                          paper_bgcolor="rgba(0,0,0,0)",
                          yaxis=dict(gridcolor="#F0E6D3"), legend_title="")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.info("💾 **To save your data permanently:** use the **Export data** button in the sidebar, then upload that JSON file back anytime to restore your counts.")
