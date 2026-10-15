# Dependency Rescue

Dependency Rescue scans public GitHub repositories for Python dependency
declarations, candidate imports and calls, and differing dependency
constraints. It presents the findings in a Streamlit app and creates a
downloadable PDF report.

## Run on Windows

From this project folder, activate the virtual environment and install the
dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Start the app:

```powershell
python -m streamlit run app.py
```

Open the local URL printed in the terminal, usually `http://localhost:8501`.
Enter an HTTPS URL for a public `github.com` repository and select **Scan
repository**.

Gemma suggestions are optional. Enter a Gemini API key in the password field,
or set `GEMINI_API_KEY` in the environment before starting the app. When a key
is provided, dependency metadata and findings are sent to Google Gemini for
suggestions. The key is not included in the generated report.

The dependency diff table is intentionally empty until version changes are
proposed. Scanning is static analysis; it does not install dependencies or run
tests from the scanned repository.
