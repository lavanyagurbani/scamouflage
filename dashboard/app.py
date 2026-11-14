"""Run from the repository root: python -m streamlit run dashboard/app.py"""
from datetime import datetime, timedelta, timezone
import os

import pandas as pd
import streamlit as st

from dashboard.bigquery_reader import DashboardError, read_query, validate_project
from dashboard.queries import DIMENSIONS, PROJECT, QuerySpec, SUPPORTED_QUESTIONS, match_question


@st.cache_data(ttl=600, max_entries=32, show_spinner=False)
def cached_read(spec, project):
    return read_query(spec, project), datetime.now(timezone.utc)


def load(spec, project):
    with st.spinner('Reading analytics from BigQuery…'):
        rows, fetched_at = cached_read(spec, project)
    st.caption('Data read at ' + fetched_at.strftime('%H:%M:%S UTC') + ' · cached for up to 10 minutes')
    return pd.DataFrame(rows)


def metric_cards(items):
    for column, (label, value) in zip(st.columns(len(items)), items):
        with column, st.container(border=True):
            st.metric(label, value)


def percent(value):
    return 'Unavailable' if pd.isna(value) else f'{float(value):.2%}'


def overview(project):
    st.subheader('The snapshot at a glance')
    row = load(QuerySpec('overview'), project).iloc[0]
    metric_cards([
        ('Job postings', f"{int(row['total_postings']):,}"),
        ('Fraudulent labels', f"{int(row['fraudulent_postings']):,}"),
        ('Job fraud rate', percent(row['fraud_rate'])),
        ('Phishing reports', f"{int(row['phishing_reports']):,}"),
    ])
    left, right = st.columns([3, 2])
    with left, st.container(border=True):
        st.markdown('#### Job label distribution')
        labels = pd.DataFrame({
            'Label': ['Non-fraudulent', 'Fraudulent', 'Unknown'],
            'Postings': [row['non_fraudulent_postings'], row['fraudulent_postings'], row['unknown_label_postings']],
        }).set_index('Label')
        st.bar_chart(labels, color='#16a085', use_container_width=True)
    with right, st.container(border=True):
        st.markdown('#### Read the numbers in context')
        st.write('Fraud rates use postings with a known source label. They describe this dataset, not a prediction.')
        st.metric('Known job labels', f"{int(row['labeled_postings']):,}")
        st.metric('Phishing target categories', f"{int(row['target_count']):,}")
        st.text(f"Submission dates: {row['first_date']} to {row['last_date']}")
        st.caption('Phishing counts are historical snapshot reports. Verified/online flags are source status, not live checks.')


def jobs(project):
    st.subheader('Explore job fraud patterns')
    st.caption('Compare one dimension at a time. Locations are the complete source strings; no geography is inferred.')
    controls = st.columns([2, 2, 1])
    dimension = controls[0].selectbox('Break down by', list(DIMENSIONS), format_func=DIMENSIONS.get)
    ranking = controls[1].selectbox('Rank by', ['Fraud rate (%)', 'Fraudulent postings', 'Total postings'])
    minimum = controls[2].number_input('Min. labeled postings', min_value=1, value=25, step=1)
    frame = load(QuerySpec('patterns', (('dimension', dimension),)), project)
    if frame.empty:
        st.info('No categories are available for this dimension.')
        return
    frame['Category'] = frame['dimension_value'].fillna('(Missing value)')
    search = st.text_input('Find a category', placeholder='Optional text filter; applied locally')
    frame = frame[frame['labeled_postings'] >= minimum]
    if search:
        frame = frame[frame['Category'].str.contains(search, case=False, regex=False)]
    if frame.empty:
        st.info('No categories match these filters. Lower the minimum or clear the text filter.')
        return
    total, labeled, fraudulent = (int(frame[c].sum()) for c in ['total_postings', 'labeled_postings', 'fraudulent_postings'])
    metric_cards([('Matching postings', f'{total:,}'), ('Fraudulent labels', f'{fraudulent:,}'),
                  ('Matching fraud rate', percent(fraudulent / labeled if labeled else None))])
    top_n = st.slider('Categories to show', 5, 30, 10)
    key = {'Fraud rate (%)': 'fraud_rate', 'Fraudulent postings': 'fraudulent_postings', 'Total postings': 'total_postings'}[ranking]
    ranked = frame.sort_values([key, 'total_postings', 'Category'], ascending=[False, False, True]).head(top_n).copy()
    ranked['Fraud rate (%)'] = ranked['fraud_rate'] * 100
    chart_key = 'Fraud rate (%)' if key == 'fraud_rate' else key
    st.bar_chart(ranked.set_index('Category')[[chart_key]], color='#d97757', use_container_width=True)
    st.caption('Cards cover all matching categories; the chart and table show only the top categories. Small samples can have unstable rates.')
    st.dataframe(ranked[['Category', 'total_postings', 'labeled_postings', 'fraudulent_postings', 'Fraud rate (%)']],
                 hide_index=True, use_container_width=True,
                 column_config={'Category': st.column_config.TextColumn('Category'),
                                'Fraud rate (%)': st.column_config.NumberColumn(format='%.2f')})


def phishing(project):
    st.subheader('Phishing report trends')
    st.caption('Aggregated report counts only. Source statuses do not indicate present-day URL safety.')
    frame = load(QuerySpec('phishing'), project)
    if frame.empty:
        st.info('The phishing mart contains no report groups.')
        return
    frame['submission_date'] = pd.to_datetime(frame['submission_date'])
    if frame['submission_date'].isna().any():
        st.warning('Some report groups have no submission date and cannot appear on a time chart.')
    dated = frame.dropna(subset=['submission_date'])
    if dated.empty:
        st.info('No dated report groups are available. Review the dbt timestamp checks.')
        return
    start, end = dated['submission_date'].min().date(), dated['submission_date'].max().date()
    columns = st.columns([2, 3])
    selected_dates = columns[0].date_input('Submission dates (UTC)',
                                         value=(max(start, end - timedelta(days=89)), end),
                                         min_value=start, max_value=end)
    targets = columns[1].multiselect('Target categories', sorted(frame['target'].dropna().unique()),
                                    placeholder='All targets')
    flags = st.columns(2)
    verified = flags[0].selectbox('Verified in source snapshot', ['All', 'Yes', 'No', 'Unknown'])
    online = flags[1].selectbox('Online in source snapshot', ['All', 'Yes', 'No', 'Unknown'])
    if len(selected_dates) != 2:
        st.info('Choose both a start and an end date.')
        return
    first, last = selected_dates
    selected = dated[(dated['submission_date'].dt.date >= first) & (dated['submission_date'].dt.date <= last)]
    if targets:
        selected = selected[selected['target'].isin(targets)]
    for choice, column in [(verified, 'is_verified'), (online, 'is_online')]:
        if choice != 'All':
            selected = selected[selected[column].isna() if choice == 'Unknown' else selected[column].eq(choice == 'Yes')]
    if selected.empty:
        st.info('No report groups match these filters.')
        return
    metric_cards([('Reports in selection', f"{int(selected['report_count'].sum()):,}"),
                  ('Target categories', f"{selected['target'].nunique():,}")])
    daily = selected.groupby('submission_date')['report_count'].sum().reindex(pd.date_range(first, last), fill_value=0)
    st.line_chart(daily.rename('Reports'), color='#16a085', use_container_width=True)
    st.caption('Dates with no matching records show zero reports in this snapshot, not zero real-world phishing activity.')
    st.markdown('#### Most reported targets in selection')
    totals = selected.groupby('target', dropna=False)['report_count'].sum().sort_values(ascending=False).head(10)
    st.bar_chart(totals.rename('Reports'), color='#d97757', use_container_width=True)
    st.dataframe(daily.rename_axis('Date').reset_index(name='Reports'), hide_index=True, use_container_width=True)


def answer(question, rows):
    """Format only actual returned aggregates; never fill an answer with demo values."""
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {'text': 'No matching analytics data was returned.', 'data': None}
    if question.kind in ('job_total', 'job_rate', 'phishing_total'):
        row = frame.iloc[0]
        if question.kind == 'job_total':
            text = f"The snapshot contains {int(row['total_postings']):,} job postings."
        elif question.kind == 'phishing_total':
            text = f"The snapshot contains {int(row['phishing_reports']):,} phishing reports."
        else:
            text = (f"The source-label fraud rate is {percent(row['fraud_rate'])}: "
                    f"{int(row['fraudulent_postings']):,} fraudulent postings out of {int(row['labeled_postings']):,} labeled postings. "
                    f"Unknown labels: {int(row['unknown_label_postings']):,}.")
        return {'text': text, 'data': None}
    if question.kind == 'patterns':
        # Rank by fraud count, not by unstable small-category rates.
        frame['Category'] = frame['dimension_value'].fillna('(Missing value)')
        frame['Fraud rate (%)'] = frame['fraud_rate'] * 100
        result = frame.sort_values(['fraudulent_postings', 'total_postings', 'Category'], ascending=[False, False, True]).head(10)
        return {'text': 'Top 10 categories by fraudulent posting count. Rates use known labels; compare the denominators.',
                'data': result[['Category', 'total_postings', 'labeled_postings', 'fraudulent_postings', 'Fraud rate (%)']]}
    if question.kind == 'targets':
        result = frame.groupby('target', dropna=False)['report_count'].sum().sort_values(ascending=False).head(10)
        return {'text': 'Top 10 targets by report count across the snapshot.', 'data': result.reset_index()}
    result = frame.groupby('submission_date', dropna=False)['report_count'].sum().reset_index()
    return {'text': 'Reports by UTC submission date in the snapshot; dates without records are omitted.', 'data': result}


def conversation(project):
    st.subheader('Ask Scamouflage')
    st.caption('Guided questions, answered from fixed analytics queries. No LLM or free-form SQL.')
    with st.expander('Supported questions', expanded=True):
        for example in SUPPORTED_QUESTIONS:
            st.text(example)
        st.caption('For a target question, replace <name> with the exact target name, without trailing punctuation. Matching is case-insensitive. Answers use the whole snapshot, independent of chart filters.')
    history = st.session_state.setdefault('conversation', [])
    if st.button('Clear conversation'):
        history.clear()
    prompt = st.chat_input('Try: What is the job fraud rate?', max_chars=500)
    if prompt:
        question = match_question(prompt)
        response = {'text': 'Unsupported question. Please use one of the documented questions above.', 'data': None}
        if question:
            try:
                with st.spinner('Reading the matching analytics…'):
                    rows, fetched_at = cached_read(question.query, project)
                response = answer(question, rows)
                response['text'] += ' Data read at ' + fetched_at.strftime('%H:%M:%S UTC') + '.'
            except DashboardError as exc:
                response = {'text': str(exc), 'data': None}
        history.append({'prompt': prompt, **response})
        del history[:-8]
    if not history:
        st.info('Choose a supported question to begin. Unsupported questions do not submit a query.')
    for message in history:
        with st.chat_message('user'):
            st.text(message['prompt'])  # Inert text: no user-supplied Markdown/links.
        with st.chat_message('assistant'):
            st.text(message['text'])
            if message['data'] is not None:
                data = message['data']
                st.dataframe(data, hide_index=True, use_container_width=True,
                             column_config={c: st.column_config.TextColumn(c) for c in data.select_dtypes(include='object').columns})


def main():
    st.set_page_config(page_title='Scamouflage | Fraud analytics', page_icon='🛡️', layout='wide')
    # Static styling only; no source values or user input is injected into HTML.
    st.markdown('''<style>
        .block-container {max-width: 1280px; padding-top: 2rem;}
        [data-testid="stMetricValue"] {color: #169b87;}
        [data-testid="stSidebar"] {border-right: 1px solid #dae8e4;}
        h1 {letter-spacing: -0.04em;}
        </style>''', unsafe_allow_html=True)
    st.title('Scamouflage')
    st.caption('FRAUD ANALYTICS / Evidence from job labels and phishing report snapshots')
    with st.sidebar:
        st.markdown('### Scamouflage')
        st.caption('Local analytics workspace')
        page = st.radio('Explore', ['Overview', 'Job fraud', 'Phishing trends', 'Ask Scamouflage'])
        st.divider()
        st.markdown('**Data source: BigQuery Sandbox**')
        st.text('scamouflage · US\nscamouflage_analytics')
        st.caption('Read-only analytics · ADC authentication\n100 MiB cap per query · 10-minute cache')
        if st.button('Refresh cached analytics', use_container_width=True):
            cached_read.clear()
        st.caption('Refreshing clears the cache; the next data request submits a new read. Chat history retains earlier answers.')
    project = os.environ.get('GCP_PROJECT_ID', '')
    try:
        validate_project(project)
        {'Overview': overview, 'Job fraud': jobs, 'Phishing trends': phishing,
         'Ask Scamouflage': conversation}[page](project)
    except DashboardError as exc:
        st.error(str(exc))
        st.info('No substitute data is shown. Restore access and use Refresh cached analytics to try again.')
    st.divider()
    st.caption('Completed: Airbyte File → SQLite full sync; separate Python batch bridge → verified BigQuery Sandbox proof tables. Airflow independently orchestrated existing ingestion → dbt run → dbt test.')


if __name__ == '__main__':
    main()
