"""Bengaluru Urban Rainfall Dashboard (Streamlit).

Run:  pip install -r requirements.txt
      streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Bengaluru Urban Rainfall Dashboard",
                   page_icon="🌧️", layout="wide")

# ---------------------------------------------------------------- settings
ADMIN_EMAIL = "adminuser12@gmail.com"
ADMIN_PASSWORD = "1122334455"
DATA_DIR = Path(__file__).parent / "data"
TALUKS = ["Anekal", "Bengaluru North", "Bengaluru South", "Bengaluru East", "Yelahanka"]
SEASONS = ["Annual", "Pre-monsoon", "SW monsoon", "NE monsoon"]
YEARS = [2022, 2023, 2024]
BLUE, GREY, RED, GREEN, VIOLET = "#0ea5e9", "#94a3b8", "#f43f5e", "#10b981", "#8b5cf6"
VALUE_COLS = [f"{s} {k}" for s in SEASONS for k in ("Normal", "Actual")]

# ---------------------------------------------------------------- data
def _unique(seen: set, name: str) -> str:
    """Two hoblis are both called Sarjapura_1 in the source; rename the repeat."""
    if name in seen:
        name = name.rsplit("_", 1)[0] + "_2"
    seen.add(name)
    return name


@st.cache_data
def load_data() -> pd.DataFrame:
    rows = []

    # 2022 file: has a serial number (1 = Anekal, 2 = North, ...) and no Category column.
    cols_2022 = ["Annual Normal (mm)", "Annual Actual (mm)", "Pre-Monsoon Normal (mm)",
                 "Pre-Monsoon Actual (mm)", "SWM Normal (mm)", "SWM Actual (mm)",
                 "NEM Normal (mm)", "NEM Actual (mm)"]
    df = pd.read_csv(DATA_DIR / "rainfall_2022.csv")
    seen: set = set()
    for _, r in df.iterrows():
        sl = r["Sl no"]
        if pd.isna(sl) or sl == int(sl):          # district / taluk total rows
            continue
        rows.append({"Year": 2022, "Hobli": _unique(seen, r["District/Taluk/Hobli"].strip()),
                     "Taluk": TALUKS[int(sl) - 1],
                     **dict(zip(VALUE_COLS, (float(r[c]) for c in cols_2022)))})

    # 2023 and 2024 files: a Category column says District / Taluk / Hobli.
    cols_new = ["Annual Normal", "Annual Actual", "Pre-Monsoon Normal", "Pre-Monsoon Actual",
                "SW Monsoon Normal", "SWM Actual", "NE Monsoon Normal", "NEM Actual"]
    for year in (2023, 2024):
        df = pd.read_csv(DATA_DIR / f"rainfall_{year}.csv", encoding="utf-8-sig")
        seen, taluk = set(), -1
        for _, r in df.iterrows():
            if r["Category"] == "Taluk":
                taluk += 1
            elif r["Category"] == "Hobli":
                rows.append({"Year": year, "Hobli": _unique(seen, r["District/Taluk/Hobli"].strip()),
                             "Taluk": TALUKS[taluk],
                             **dict(zip(VALUE_COLS, (float(r[c]) for c in cols_new)))})
    return pd.DataFrame(rows)


def departure(normal: float, actual: float) -> float:
    """Percentage departure from normal, from averages (not an average of percentages)."""
    return (actual - normal) / normal * 100


def status(dep: float) -> str:
    return "Deficient" if dep <= -20 else "Excess" if dep >= 20 else "Normal"


STATUS_COLOUR = {"Deficient": RED, "Normal": GREY, "Excess": BLUE}

# ---------------------------------------------------------------- login
def login_page() -> None:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.title("🌧️ Rainfall Insights")
        st.caption("Anekal · Bengaluru Urban · Admin sign-in")
        with st.form("login"):
            email = st.text_input("Admin email")
            # type="password" gives a built-in eye icon to show / hide the password
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in", width="stretch"):
                if email.strip().lower() == ADMIN_EMAIL and password == ADMIN_PASSWORD:
                    st.session_state["admin"] = True
                    st.rerun()
                st.error("Access denied. Only the admin account can sign in.")


# ---------------------------------------------------------------- dashboard
def dashboard() -> None:
    data = load_data()
    top = st.columns([6, 1])
    top[0].title("Bengaluru Urban Rainfall Dashboard")
    top[0].caption("Welcome, Admin")
    if top[1].button("Log out"):
        st.session_state["admin"] = False
        st.rerun()

    # ---- slicers
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.3, 2.6, 1.8])
        year_pick = c1.radio("Year", ["All Years"] + YEARS, horizontal=True)
        taluk_pick = c2.radio("Taluk", ["All taluks"] + TALUKS, horizontal=True)
        season = c3.radio("Season", SEASONS, horizontal=True)

    N, A = f"{season} Normal", f"{season} Actual"
    sel = data.copy()
    if year_pick != "All Years":
        sel = sel[sel["Year"] == year_pick]
    if taluk_pick != "All taluks":
        sel = sel[sel["Taluk"] == taluk_pick]
    if sel.empty:
        st.warning("No data for this combination. The 2022 file has no Yelahanka hobli rows.")
        return

    sel = sel.assign(Dep=(sel[A] - sel[N]) / sel[N] * 100)
    sel["Status"] = sel["Dep"].map(status)
    n, a = sel[N].mean(), sel[A].mean()
    dp = departure(n, a)
    counts = sel["Status"].value_counts().reindex(["Deficient", "Normal", "Excess"], fill_value=0)
    lo, hi = sel.loc[sel["Dep"].idxmin()], sel.loc[sel["Dep"].idxmax()]

    # ---- KPI cards
    k = st.columns(6)
    k[0].metric("Avg normal rainfall", f"{n:.0f} mm")
    k[1].metric("Avg actual rainfall", f"{a:.0f} mm")
    k[2].metric("Departure", f"{dp:+.1f}%")
    k[3].metric("Deficient records", f"{counts['Deficient']} of {len(sel)}")
    k[4].metric("Driest", f"{lo['Hobli']} ({lo['Year']})", f"{lo['Dep']:+.1f}%")
    k[5].metric("Wettest", f"{hi['Hobli']} ({hi['Year']})", f"{hi['Dep']:+.1f}%")

    # ---- charts
    left, right = st.columns(2)

    by = "Taluk" if taluk_pick == "All taluks" else "Hobli"
    g = sel.groupby(by, sort=False)[[N, A]].mean().round().reset_index()
    fig = px.bar(g.melt(by, var_name="Type", value_name="mm"), x=by, y="mm", color="Type",
                 barmode="group", color_discrete_sequence=[GREY, BLUE],
                 title=f"{season} rainfall: normal vs actual by {by.lower()} (mm)")
    fig.for_each_trace(lambda t: t.update(name=t.name.split()[-1]))
    left.plotly_chart(fig, width="stretch")

    d = (sel.groupby("Hobli")[[N, A]].mean().assign(Dep=lambda x: (x[A] - x[N]) / x[N] * 100)
         .nsmallest(10, "Dep").reset_index())
    fig = px.bar(d.iloc[::-1], x="Dep", y="Hobli", orientation="h",
                 title="10 driest areas (departure from normal, %)")
    fig.update_traces(marker_color=[RED if v < 0 else GREEN for v in d.iloc[::-1]["Dep"]])
    right.plotly_chart(fig, width="stretch")

    fig = px.pie(values=counts.values, names=counts.index, hole=0.55, color=counts.index,
                 color_discrete_map=STATUS_COLOUR, title="Rainfall status of hobli records")
    left.plotly_chart(fig, width="stretch")

    seas = pd.DataFrame({"Season": SEASONS,
                         "Normal": [sel[f"{s} Normal"].mean() for s in SEASONS],
                         "Actual": [sel[f"{s} Actual"].mean() for s in SEASONS]})
    fig = px.bar(seas.melt("Season", var_name="Type", value_name="mm"), x="Season", y="mm",
                 color="Type", barmode="group", color_discrete_sequence=[GREY, VIOLET],
                 title="Normal vs actual by season (mm)")
    right.plotly_chart(fig, width="stretch")

    base = data if taluk_pick == "All taluks" else data[data["Taluk"] == taluk_pick]
    yr = {y: departure(q[N].mean(), q[A].mean()) for y, q in base.groupby("Year")}
    fig = go.Figure(go.Bar(x=[str(y) for y in yr], y=list(yr.values()),
                           marker_color=[RED if v < 0 else GREEN for v in yr.values()],
                           opacity=1))
    fig.update_traces(marker_opacity=[1 if year_pick in ("All Years", y) else 0.35 for y in yr])
    fig.update_layout(title="Departure % by year (selected year highlighted)")
    left.plotly_chart(fig, width="stretch")

    mx = max(sel[N].max(), sel[A].max())
    fig = px.scatter(sel, x=N, y=A, color="Status", color_discrete_map=STATUS_COLOUR,
                     hover_name="Hobli", title="Normal vs actual per hobli record (mm)")
    fig.add_trace(go.Scatter(x=[0, mx], y=[0, mx], mode="lines", name="Actual = normal",
                             line=dict(color=GREY, dash="dash")))
    right.plotly_chart(fig, width="stretch")

    # ---- interpretation
    st.subheader("📌 Interpretation of your selection")
    band = status(dp)
    box = {"Deficient": st.error, "Normal": st.info, "Excess": st.success}[band]
    box(f"**{year_pick} · {taluk_pick} · {season}** — {band if band != 'Normal' else 'Within the normal band'}: "
        f"average rainfall was **{a:.0f} mm** against a normal of **{n:.0f} mm** "
        f"(departure **{dp:+.1f}%**).")
    pct = (counts / len(sel) * 100).round()
    st.write(f"🔴 Deficient **{counts['Deficient']}** ({pct['Deficient']:.0f}%) · "
             f"⚪ Normal **{counts['Normal']}** ({pct['Normal']:.0f}%) · "
             f"🔵 Excess **{counts['Excess']}** ({pct['Excess']:.0f}%)")
    st.write(f"🏜️ **Driest:** {lo['Hobli']} ({lo['Year']}) at {lo['Dep']:+.1f}%")
    st.write(f"🌧️ **Wettest:** {hi['Hobli']} ({hi['Year']}) at {hi['Dep']:+.1f}%")
    st.caption("Departure uses average actual vs average normal, not an average of percentages.")

    # ---- conclusion
    st.subheader("✅ Conclusion")
    ann = {y: departure(q["Annual Normal"].mean(), q["Annual Actual"].mean())
           for y, q in data.groupby("Year")}
    cards = st.columns(3)
    with cards[0].container(border=True):
        st.markdown("**📊 Big swings between years**")
        st.write("Average annual departure across hoblis moved between wet and dry extremes, "
                 "so one year does not describe the climate.")
        st.write("  ".join(f"`{y}: {v:+.1f}%`" for y, v in ann.items()))
    with cards[1].container(border=True):
        st.markdown("**📍 Local differences matter**")
        st.write("Departures vary widely inside the same year, and in the dry year 2023 a few "
                 "hoblis stayed close to normal. Hobli-level data beats the district average.")
    with cards[2].container(border=True):
        st.markdown("**🗓️ Seasons tell different stories**")
        st.write("Annual totals can hide seasonal swings. Use the season slicer to compare "
                 "pre-monsoon, SW monsoon and NE monsoon.")
    cards = st.columns(2)
    with cards[0].container(border=True):
        st.markdown("**🏞️ Anekal context (Paani.Earth map)**")
        st.write("1046 mm 40-year average rain · 285 lakes (3+ acres) · 27 minor irrigation lakes "
                 "(794.28 MCFt) · groundwater 100% overexploited · 5,17,575 people (2011) · 533 sq km. "
                 "With groundwater already overexploited, deficient years put extra pressure on lake "
                 "storage and recharge.")
    with cards[1].container(border=True):
        st.markdown("**⚠️ Limits**")
        st.write("Three years are not a full climate record, 2022 has no Yelahanka hobli rows, and "
                 "rainfall alone does not show runoff, evaporation or lake inflow.")
    st.caption("Data: KSNDMC district rainfall files for 2022–2024 (by hobli) plus context from the "
               "Paani.Earth Anekal map (CC BY-NC-SA). Status bands: deficient ≤ −20%, excess ≥ +20%.")


# ---------------------------------------------------------------- entry point
if st.session_state.get("admin"):
    dashboard()
else:
    login_page()
