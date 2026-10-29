"""入口：streamlit run app.py"""
import streamlit as st

from config import APP_ICON, APP_TITLE
from features import FEATURES

st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")

pages = [
    st.Page(f.render, title=f.title, icon=f.icon,
            url_path=None if f.default else f.slug, default=f.default)
    for f in FEATURES
]

st.sidebar.title(f"{APP_ICON} {APP_TITLE}")
st.navigation(pages).run()
