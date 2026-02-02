import streamlit as st
import requests

API_BASE = "http://localhost:8000"

st.title("CORS demo: Streamlit → FastAPI")

if st.button("GET /employees"):
    r = requests.get(f"{API_BASE}/employees", timeout=10)
    st.write("Status:", r.status_code)
    st.json(r.json())

st.divider()

name = st.text_input("Name", "Navneet")
salary = st.number_input("Salary", 60000, step=1000)

if st.button("POST /echo"):
    payload = {"name": name, "salary": int(salary)}
    r = requests.post(f"{API_BASE}/echo", json=payload, timeout=10)
    st.write("Status:", r.status_code)
    st.json(r.json())
# Important nuance:
# If Streamlit calls FastAPI using Python requests (server-to-server), CORS is NOT enforced, because CORS is a browser rule.
# CORS matters when the browser makes the request (JS fetch, XHR).
# So to truly see CORS in action, we should make a request from the browser side.