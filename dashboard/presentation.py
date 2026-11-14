"""Dashboard theme tokens and chart specs. No data access or Streamlit imports."""
THEME_KEY = 'pearl_theme'
THEMES = {
    'Light': {'background': '#F8F8FA', 'surface': '#FFFFFF', 'border': '#E9E7ED',
              'text': '#24202C', 'accent': '#62429A', 'muted': '#585260',
              'tint': '#F0ECF7', 'secondary': '#827092'},
    'Dark': {'background': '#111116', 'surface': '#1C1C24', 'border': '#303039',
             'text': '#F4F2F8', 'accent': '#B9A0F5', 'muted': '#BEB8CA',
             'tint': '#282333', 'secondary': '#A69ABF'},
}
PAGES = ('Overview', 'Job Fraud Analytics', 'Phishing Intelligence', 'Ask Scamouflage', 'Pipeline Status')
PAGE_DESCRIPTIONS = {
    'Overview': 'Job fraud labels and historical phishing report counts.',
    'Job Fraud Analytics': 'Fraud rates and sample sizes by source category.',
    'Phishing Intelligence': 'Report counts by date, target, and source status.',
    'Ask Scamouflage': 'Supported questions mapped to fixed, read-only analytics queries.',
    'Pipeline Status': 'Recorded pipeline verification results; no live health checks.',
}


def selected_theme(state):
    if state.get(THEME_KEY) not in THEMES:
        state[THEME_KEY] = 'Light'
    return state[THEME_KEY]


def tokens(mode):
    return dict(THEMES[mode])  # Callers cannot mutate the shared palette.


def chart_spec(mode, kind, x_field, y_field, secondary=False):
    """Theme only; caller supplies unchanged chart data and aggregation results."""
    palette = tokens(mode)
    axis = {'labelColor': palette['muted'], 'titleColor': palette['text'],
            'gridColor': palette['border'], 'tickColor': palette['border'],
            'domain': False, 'labelFontSize': 12, 'titleFontSize': 12,
            'titleFontWeight': 500, 'labelPadding': 8, 'titlePadding': 14}
    spec = {
        'background': palette['surface'], 'height': 300,
        'padding': {'top': 16, 'right': 20, 'bottom': 8, 'left': 8},
        'config': {'view': {'stroke': None}, 'axis': axis,
                   'font': '-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
                   'legend': {'labelColor': palette['text'], 'titleColor': palette['text']}},
    }
    color = palette['secondary' if secondary else 'accent']
    if kind == 'bar':
        spec.update({
            'mark': {'type': 'bar', 'color': color, 'cornerRadiusEnd': 3},
            'encoding': {
                'y': {'field': x_field, 'type': 'nominal', 'sort': None, 'title': None,
                      'axis': {'labelLimit': 180, 'grid': False}},
                'x': {'field': y_field, 'type': 'quantitative', 'title': y_field},
                'tooltip': [{'field': x_field, 'type': 'nominal'},
                            {'field': y_field, 'type': 'quantitative'}],
            },
        })
    elif kind == 'line':
        spec.update({
            'mark': {'type': 'line', 'color': color, 'strokeWidth': 2.5, 'clip': True},
            'encoding': {
                'x': {'field': x_field, 'type': 'temporal', 'title': 'Submission date (UTC)',
                      'axis': {'format': '%d %b', 'grid': False}},
                'y': {'field': y_field, 'type': 'quantitative', 'title': y_field,
                      'scale': {'zero': True}},
                'tooltip': [{'field': x_field, 'type': 'temporal', 'title': 'Date'},
                            {'field': y_field, 'type': 'quantitative'}],
            },
        })
    else:
        raise ValueError('Unsupported chart kind')
    return spec


def stylesheet(mode):
    p = tokens(mode)
    # Only trusted static palette values enter CSS; no data/user text enters HTML.
    return '''<style>
    [data-testid="stApp"], body:has(.st-key-pearl-theme-toggle) {
        --pf-bg: %(background)s; --pf-surface: %(surface)s; --pf-border: %(border)s;
        --pf-text: %(text)s; --pf-accent: %(accent)s; --pf-muted: %(muted)s; --pf-tint: %(tint)s;
        background: var(--pf-bg); color: var(--pf-text);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color-scheme: %(scheme)s;
    }
    [data-testid="stAppViewContainer"], [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {background: var(--pf-bg); color: var(--pf-text);}
    [data-testid="stMainBlockContainer"] {max-width: 1280px; padding: 1.3rem 2.8rem 2rem;}
    [data-testid="stHeader"] {background: var(--pf-bg); border-bottom: 1px solid var(--pf-border);}
    /* Presentation chrome only: retain the header, sidebar toggle and diagnostics. */
    [data-testid="stAppDeployButton"], [data-testid="stMainMenu"] {display: none;}
    .st-key-pearl-theme-toggle {padding-top: .15rem;}
    [data-testid="stApp"] h1, [data-testid="stApp"] h2,
    [data-testid="stApp"] h3, [data-testid="stApp"] h4,
    [data-testid="stMarkdownContainer"], [data-testid="stText"],
    [data-testid="stWidgetLabel"] p {color: var(--pf-text);}
    [data-testid="stApp"] h1 {font-size: 2.2rem; font-weight: 650; letter-spacing: -.055em; padding-bottom: .2rem;}
    [data-testid="stApp"] h2 {font-size: 1.45rem; font-weight: 600; letter-spacing: -.025em;}
    [data-testid="stApp"] h3 {font-size: 1.15rem; font-weight: 600; letter-spacing: -.015em;}
    [data-testid="stApp"] h4 {font-size: 1rem; font-weight: 600;}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
        color: var(--pf-muted); line-height: 1.6; font-size: .82rem;
    }
    [data-testid="stSidebar"] {background: var(--pf-surface); border-right: 1px solid var(--pf-border);}
    [data-testid="stSidebarUserContent"] {padding-top: 2.2rem;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        border-radius: 8px; padding: .55rem .65rem; margin-bottom: .15rem;
        transition: background-color 120ms ease;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {background: var(--pf-tint);}
    /* Hide only the decorative indicator; retain the native input and radio semantics. */
    [data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] > div:first-child {
        opacity: 0; position: absolute; width: 0; margin: 0;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:focus-within {
        outline: 2px solid var(--pf-accent); outline-offset: 2px;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
        background: var(--pf-tint); box-shadow: inset 3px 0 var(--pf-accent);
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p {color: var(--pf-accent); font-weight: 600;}
    [data-testid="stVerticalBlockBorderWrapper"] > div {
        background: var(--pf-surface); border-color: var(--pf-border) !important;
        border-radius: 12px !important;
    }
    [class*="st-key-pearl-kpi-"] {
        min-height: 116px; background: var(--pf-surface);
        border: 1px solid var(--pf-border) !important; border-radius: 12px !important;
        padding: 1.15rem 1.25rem !important; box-shadow: 0 2px 8px rgba(24, 16, 40, .035);
    }
    [data-testid="stMetricLabel"] p {color: var(--pf-muted); font-size: .8rem; font-weight: 500;}
    [data-testid="stMetricValue"] {color: var(--pf-text); font-size: 1.9rem; font-weight: 600; letter-spacing: -.04em;}
    [data-testid="stApp"] hr {border-color: var(--pf-border); margin: 1.3rem 0;}
    [data-testid="stApp"] a {color: var(--pf-accent);}
    [data-testid="stApp"] code {background: var(--pf-tint); color: var(--pf-text);}
    [data-testid="stApp"] [data-baseweb="input"],
    [data-testid="stApp"] [data-baseweb="select"] > div,
    [data-testid="stApp"] [data-baseweb="textarea"] {
        background: var(--pf-surface); border-color: var(--pf-border); color: var(--pf-text); border-radius: 8px;
    }
    [data-testid="stApp"] input, [data-testid="stApp"] textarea,
    [data-testid="stApp"] [data-baseweb="select"] span {color: var(--pf-text); -webkit-text-fill-color: var(--pf-text);}
    [data-testid="stApp"] input::placeholder, [data-testid="stApp"] textarea::placeholder {
        color: var(--pf-muted); -webkit-text-fill-color: var(--pf-muted);
    }
    [data-testid="stApp"] button {
        background: var(--pf-surface); color: var(--pf-text); border-color: var(--pf-border);
        border-radius: 8px; font-weight: 500; transition: border-color 120ms ease;
    }
    [data-testid="stApp"] button:hover {color: var(--pf-accent); border-color: var(--pf-accent);}
    [data-testid="stApp"] button:focus-visible, [data-testid="stApp"] input:focus-visible {
        outline: 2px solid var(--pf-accent); outline-offset: 3px;
    }
    [data-testid="stApp"] input[type="radio"] {accent-color: var(--pf-accent);}
    [data-testid="stApp"] [data-baseweb="radio"]:has(input:checked) > div:first-child {
        background-color: var(--pf-accent); border-color: var(--pf-accent);
    }
    [data-testid="stApp"] [data-baseweb="slider"] [role="slider"] {background-color: var(--pf-accent);}
    [data-testid="stApp"] [data-testid="stThumbValue"] {color: var(--pf-accent);}
    body:has(.st-key-pearl-theme-toggle) [data-baseweb="popover"] > div,
    body:has(.st-key-pearl-theme-toggle) [role="listbox"],
    body:has(.st-key-pearl-theme-toggle) [role="option"],
    body:has(.st-key-pearl-theme-toggle) [data-baseweb="calendar"] {
        background: var(--pf-surface); color: var(--pf-text); border-color: var(--pf-border);
    }
    body:has(.st-key-pearl-theme-toggle) [role="option"]:hover,
    body:has(.st-key-pearl-theme-toggle) [role="option"][aria-selected="true"] {
        background: var(--pf-tint); color: var(--pf-accent);
    }
    body:has(.st-key-pearl-theme-toggle) #vg-tooltip-element {
        background: var(--pf-surface); color: var(--pf-text); border-color: var(--pf-border);
    }
    [data-testid="stApp"] [data-testid="stExpander"] {
        background: var(--pf-surface); border-color: var(--pf-border); border-radius: 10px;
    }
    [data-testid="stApp"] [data-testid="stExpander"] details summary {color: var(--pf-text);}
    [data-testid="stChatMessage"] {background: var(--pf-surface); border: 1px solid var(--pf-border); border-radius: 12px;}
    [data-testid="stChatInput"] {background: var(--pf-surface); border: 1px solid var(--pf-border);}
    [data-testid="stBottom"], [data-testid="stBottomBlockContainer"] {background: var(--pf-bg);}
    [data-testid="stApp"] [data-testid="stAlert"] {background: var(--pf-tint); color: var(--pf-text); border-color: var(--pf-border);}
    .st-key-pearl-theme-toggle [data-testid="stRadio"] > div {gap: 4px; background: var(--pf-tint); padding: 4px; border-radius: 9px;}
    .st-key-pearl-theme-toggle [data-testid="stRadio"] label {margin: 0; padding: .3rem .65rem; border-radius: 6px;}
    .st-key-pearl-theme-toggle [data-testid="stRadio"] label:has(input:checked) {background: var(--pf-surface);}
    .st-key-pearl-theme-toggle [data-testid="stRadio"] label:has(input:checked) p {color: var(--pf-accent);}
    @media (max-width: 760px) {
        [data-testid="stMainBlockContainer"] {padding: 1.5rem 1rem;}
        [data-testid="stMetricValue"] {font-size: 1.55rem;}
        [data-testid="stApp"] h1 {font-size: 1.85rem;}
        .st-key-pearl-kpis [data-testid="stHorizontalBlock"] {flex-wrap: wrap;}
        .st-key-pearl-kpis [data-testid="stColumn"] {min-width: 44%%; flex: 1 1 44%%;}
    }
    @media (prefers-reduced-motion: reduce) {
        [data-testid="stApp"] button, [data-testid="stSidebar"] label {transition: none;}
    }
    </style>''' % {**p, 'scheme': mode.lower()}
