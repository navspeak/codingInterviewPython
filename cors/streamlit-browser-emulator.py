import streamlit as st
import streamlit.components.v1 as components

components.html(
    """
    <h4>Browser fetch() to FastAPI (this triggers CORS)</h4>
    <button onclick="callApi()">Fetch employees</button>
    <pre id="out"></pre>

    <script>
      async function callApi() {
        const out = document.getElementById("out");
        out.textContent = "Calling...";
        try {
          const resp = await fetch("http://localhost:8000/employees", {
            method: "GET",
            // Try adding headers to trigger preflight:
            // headers: { "X-Demo": "1" }
          });
          const data = await resp.json();
          out.textContent = JSON.stringify(data, null, 2);
        } catch (e) {
          out.textContent = "ERROR: " + e;
        }
      }
    </script>
    """,
    height=250,
)
