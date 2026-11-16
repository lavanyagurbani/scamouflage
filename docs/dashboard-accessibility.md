# Global dashboard readability fix

Applied to the shared UI on 16 November 2026. No queries, ML, URL checking,
dbt, Airflow or Airbyte logic changed.

## Diagnosis

There was no project `.streamlit/config.toml`. The custom Light/Dark radio changed
CSS but did not change Streamlit's native frontend theme. Wrapper-only input rules
left actual input/textarea backgrounds to the native theme; nested text, popup
portals and canvas dataframe headers also retained native colors. Low-contrast
borders and small captions made these inconsistencies harder to read.

## Implementation

`dashboard/presentation.py` owns the semantic palettes. `dashboard/theme.css` is the
single shared stylesheet; the former embedded CSS was removed. It covers leaves
and wrappers for form controls, navigation, captions, metrics, chat, alerts,
expanders, tabs, portal menus/calendar, buttons, disabled/loading states and focus.
Shared chart specs set axes, legends, titles and marks explicitly. Existing
dataframe cell Styler colors continue to follow the application radio.

`.streamlit/config.toml` defines native light/dark palettes, base font size and
visible widget borders. Palette equality tests prevent drift between native
configuration and Python tokens. Dataframe canvas headers use the same charcoal
background and white text in both native themes, since CSS cannot repaint canvas
headers. The application radio remains session-local and does not mutate private
Streamlit APIs or the global server configuration. It is not synchronized with
Streamlit's separate native theme preference. Native-only canvas selection and
empty-grid areas therefore still need browser verification, especially when the
native preference and application radio differ.

Text tokens meet 4.5:1 against their tested surfaces; control borders meet 3:1.
Tests cover primary/secondary/status/disabled text, input text/placeholders, accent
button text and header text. These numerical checks do not establish whole-app
WCAG conformance: actual browser rendering and interaction still require review.

## Verification

Browser automation and screenshot inspection were unavailable in this environment
(no browser-control tools or installed Playwright/Selenium). AppTest renders all
six pages in both modes with synthetic offline BigQuery fixtures; it checks
exceptions, theme persistence, navigation and cached KPI/query behavior. The
checker suite separately exercises form submission, results, theme change and
validation errors using the real locally trained artifact. These tests do not
measure computed browser styles, popup rendering or pixels.

Actual results: **22 dashboard-focused tests passed** and **64 full-suite tests
passed**. The full suite includes the checker rendering/inference tests and existing
pipeline regression tests. No cloud test rerun was necessary for this UI-only change.

Run from the repository root:

```powershell
.\.venv-checker\Scripts\python.exe -m unittest discover -s tests -p 'test_dashboard*.py' -v
.\.venv-checker\Scripts\python.exe -m unittest discover -s tests -v
$env:GCP_PROJECT_ID = 'scamouflage'
.\.venv-checker\Scripts\python.exe -m streamlit run dashboard/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Restart Streamlit after changing native configuration, then reload the browser.

## Required manual visual pass

Repeat each step in **Light and Dark**, first on desktop and then at approximately
390px width. Also repeat with an opposite browser/native theme preference.

1. **All pages:** verify heading, captions, footer, sidebar selected/unselected
   navigation, appearance radio, collapsed sidebar toggle and keyboard focus. Use
   Tab/Shift+Tab, not only mouse hover. Text should not clip or overflow the page.
2. **Overview:** read all KPI values/labels, cards and bar-chart axes; hover a bar
   and read its tooltip. Check the header and cells of any tables.
3. **Check Job Link:** inspect empty placeholders, typed URL/title/description,
   primary/secondary buttons and focus outlines. Submit an example public URL with
   a full manual description, then a private URL; read results, info, warning and
   validation error. Never visit reported phishing sites.
4. **Job Fraud Analytics:** open both dropdowns, inspect selected/hovered items,
   type a category filter, change the numeric minimum/slider, hover chart marks,
   sort/scroll the dataframe and read its headers, cells and selection state.
5. **Phishing Intelligence:** open calendar and target multiselect portals, select
   tags and inspect removal icons. Change status filters, inspect line/bar chart
   axes/tooltips and scroll the daily dataframe. No data should create a readable
   informational state.
6. **Ask Scamouflage:** inspect the chat placeholder and typed question. Submit
   `What is the job fraud rate?`, then unsupported text; read both message bubbles
   and any answer table. Check send/disabled states and clear-history controls.
7. **Pipeline Status:** read every stage card and status description; verify all
   informational captions in both themes.
8. During an analytics read, inspect the spinner; with unavailable ADC, check the
   error/info messages and confirm the checker remains accessible. Check browser
   zoom at 200% and horizontal scrolling inside tables rather than across the page.

Record actual screenshots for the twelve page/theme combinations and any open
dropdown, calendar, chart tooltip and dataframe selection states before claiming
pixel-level or complete accessibility verification.
