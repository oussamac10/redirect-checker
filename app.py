import streamlit as st
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# === APP TITLE ===
st.title("🔗 Redirect Tester")
st.write("Upload an Excel (.xlsx) file with **source** and **target** columns. "
         "The app will check if each source URL correctly redirects to its target URL.")

# === FILE UPLOAD ===
uploaded_file = st.file_uploader("📤 Upload Excel file", type=["xlsx"])

TIMEOUT = 10
MAX_WORKERS = 15

def check_redirect(source, target):
    """Check if the source URL redirects to the expected target URL."""
    try:
        response = requests.head(source, allow_redirects=True, timeout=TIMEOUT)
        final_url = response.url
        status = response.status_code

        # Some servers don't support HEAD properly, fallback to GET
        if status >= 400 or status == 0:
            response = requests.get(source, allow_redirects=True, timeout=TIMEOUT)
            final_url = response.url
            status = response.status_code

        # Compare normalized URLs
        def normalize(url):
            if not url:
                return ""
            return url.strip().lower().rstrip("/")

        if status >= 400:
            return (source, target, f"❌ HTTP Fehler {status}", final_url)
        elif normalize(final_url) != normalize(target):
            return (source, target, f"⚠️ Falsche Weiterleitung (→ {final_url})", final_url)
        else:
            return (source, target, "✅ Korrekt weitergeleitet", final_url)

    except requests.exceptions.RequestException as e:
        return (source, target, f"❌ Fehler: {e}", None)


if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Look for source/target columns (case-insensitive)
    cols = [c.lower() for c in df.columns]
    if "source" not in cols or "target" not in cols:
        st.error("Excel must contain columns named **source** and **target**.")
    else:
        source_col = df.columns[cols.index("source")]
        target_col = df.columns[cols.index("target")]

        pairs = list(zip(df[source_col].dropna(), df[target_col].dropna()))
        total = len(pairs)
        st.info(f"Found {total} source–target pairs. Checking redirects...")

        results = []

        # === Progress bar ===
        progress_bar = st.progress(0)
        progress_text = st.empty()

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(check_redirect, s, t): (s, t) for s, t in pairs}
            completed = 0
            for future in as_completed(futures):
                results.append(future.result())
                completed += 1
                progress = int(completed / total * 100)
                progress_bar.progress(progress)
                progress_text.text(f"🔍 Checking... {completed}/{total} ({progress}%)")

        progress_text.text("✅ Done!")

        # Convert results into a DataFrame
        result_df = pd.DataFrame(results, columns=["Source", "Target", "Status", "Final URL"])

        # Show incorrect redirects only
        broken_df = result_df[result_df["Status"].str.startswith(("❌", "⚠️"))]

        st.subheader("📋 Ergebnis")
        if broken_df.empty:
            st.success("🎉 Alle Weiterleitungen funktionieren korrekt!")
        else:
            st.warning(f"⚠️ {len(broken_df)} fehlerhafte Weiterleitungen gefunden:")
            st.dataframe(broken_df)

            # Allow download of failed redirects
            st.download_button(
                label="⬇️ Download fehlerhafte Weiterleitungen (CSV)",
                data=broken_df.to_csv(index=False).encode("utf-8"),
                file_name="broken_redirects.csv",
                mime="text/csv"
            )
