"""Dashboard theme tokens and chart specs. No data access or Streamlit imports."""
THEME_KEY = 'pearl_theme'
THEMES = {
    'Light': {'background': '#F8F8FA', 'surface': '#FFFFFF', 'border': '#85808D',
              'text': '#24202C', 'accent': '#62429A', 'muted': '#585260',
              'tint': '#F0ECF7', 'secondary': '#735E91',
              'input': '#FFFFFF', 'input_text': '#24202C', 'placeholder': '#625D6B',
              'success': '#24643B', 'warning': '#805000', 'error': '#AD263B',
              'disabled': '#625D6B', 'on_accent': '#FFFFFF'},
    'Dark': {'background': '#111116', 'surface': '#1C1C24', 'border': '#85808D',
             'text': '#F4F2F8', 'accent': '#B9A0F5', 'muted': '#BEB8CA',
             'tint': '#282333', 'secondary': '#B3A1CB',
             'input': '#24242E', 'input_text': '#F4F2F8', 'placeholder': '#BEB8CA',
             'success': '#8CD5A4', 'warning': '#F3CA78', 'error': '#FF9EAD',
             'disabled': '#BEB8CA', 'on_accent': '#191221'},
}
PAGES = ('Overview', 'Check Job Link', 'Job Fraud Analytics', 'Phishing Intelligence', 'Ask Scamouflage', 'Pipeline Status')
PAGE_DESCRIPTIONS = {
    'Check Job Link': 'Assess a job URL and manually supplied job content using historical evidence.',
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
            'domain': False, 'labelFontSize': 13, 'titleFontSize': 14,
            'titleFontWeight': 500, 'labelPadding': 8, 'titlePadding': 14}
    spec = {
        'background': palette['surface'], 'height': 300,
        'padding': {'top': 16, 'right': 20, 'bottom': 8, 'left': 8},
        'config': {'view': {'stroke': None}, 'axis': axis,
                   'font': '-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
                   'legend': {'labelColor': palette['text'], 'titleColor': palette['text'],
                              'labelFontSize': 13, 'titleFontSize': 14},
                   'title': {'color': palette['text'], 'fontSize': 16},
                   'text': {'color': palette['text']}},
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
    from pathlib import Path
    from string import Template
    template = Path(__file__).with_name('theme.css').read_text(encoding='utf-8')
    return '<style>' + Template(template).substitute(**tokens(mode), scheme=mode.lower()) + '</style>'
