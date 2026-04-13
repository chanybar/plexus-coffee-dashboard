# ☕ Plexus Coffee Tracker

A personal field tracking tool for Plexus Technology's coffee-driven B2B outreach campaign. Log stops, rate engagements, track coffee samples given out, and visualize routes across the Phoenix metro — all in one place.

---

## What It Does

- **Route Map** — Interactive map of every business visited, color-coded by star rating
- **Stop Log** — Full history of every stop, searchable and filterable by date, stars, and industry
- **Add Stop** — Quickly log a new stop in the field with star rating and coffee counts
- **Bean Tracker** — Manual counter for whole bean and ground coffee bags given out
- **Overview** — KPIs, charts, and analytics across all route days

---

## Tech Stack

- [Streamlit](https://streamlit.io) — app framework
- [Folium](https://python-visualization.github.io/folium/) + [streamlit-folium](https://folium.streamlit.app) — interactive map
- [Plotly](https://plotly.com/python/) — charts
- [Pandas](https://pandas.pydata.org) — data handling

---

## Running Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Deploying on Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app** → select this repo → set main file to `app.py`
4. Click **Deploy**

---

## Data Persistence

Data lives in `data.json` as the seed. Changes made during a session (new stops, bean adjustments) are held in memory.

**To save your data permanently:**
1. Use the **⬇ Export data** button in the sidebar
2. Download the JSON file
3. Replace `data.json` in this repo with the exported file and push

**To restore a previous save:**
- Use the **⬆ Import data** file uploader in the sidebar

---

## File Structure

```
plexus-coffee-dashboard/
├── app.py                  # Main Streamlit app
├── data.json               # All stop + route seed data
├── requirements.txt        # Python dependencies
└── .streamlit/
    └── config.toml         # App theme (coffee palette)
```

---

## Star Rating System

| Rating | Meaning |
|--------|---------|
| ⭐⭐⭐ | Highly engaged — strong interest, great conversation |
| ⭐⭐   | Good visit — positive reception, worth a return |
| ⭐     | Low engagement — not interested or no opportunity |

---

*Built for Chandler White · Plexus Technology*
