"""Streamlit checker page, independent of cloud analytics credentials."""
import streamlit as st
from checker.assessment import assess


def render(project=None):
    st.caption('URL indicators, historical snapshot matches and job-content classification are separate checks.')
    st.info('Automatic extraction was unavailable. Paste the job description below to continue.')
    st.caption('Automatic page retrieval is disabled for SSRF safety. No submitted website is contacted. Manual text is not verified against the URL.')
    from checker.private_assets import ensure, AssetError, configuration
    from checker.diagnostics import BUILD, inspect
    st.caption('Checker build: ' + BUILD + ' | credential probe v1')
    with st.expander('Private checker diagnostics'):
        if st.button('Verify private checker setup'):
            st.session_state.pop('job_scan', None)
            with st.spinner('Checking private repository access and pinned assets...'):
                report = inspect()
                if report.get('result') == 'repository_not_accessible':
                    from checker.credential_probe import inspect as inspect_credential
                    report.update(inspect_credential(configuration()))
                st.session_state['checker_diagnostics'] = report
        if 'checker_diagnostics' in st.session_state:
            st.json(st.session_state['checker_diagnostics'])
    if configuration():
        with st.spinner('Preparing verified private checker assets...'):
            for kind in ('model', 'history'):
                try:
                    ensure(kind)
                except AssetError as exc:
                    st.warning('Private ' + kind + ' asset unavailable (' + getattr(exc, 'code', 'unavailable') + '). Check artifact settings and token access.')
    with st.form('job-link-check'):
        url = st.text_input('Job posting URL', max_chars=8192, placeholder='https://company.example/careers/job')
        title = st.text_input('Manual job title (optional)', max_chars=500)
        description = st.text_area('Manual job description (at least 40 words for ML analysis)', max_chars=100000, height=220)
        submitted = st.form_submit_button('Analyze Job Link')
    if submitted:
        st.session_state.pop('job_scan', None)
        try:
            with st.spinner('Analyzing available evidence...'):
                st.session_state['job_scan'] = assess(url, title, description)
        except ValueError as exc:
            st.error(str(exc))
    result = st.session_state.get('job_scan')
    if not result:
        return
    st.subheader(result['assessment'])
    st.text('Source hostname: ' + result['url']['host'])
    st.text('Registered domain: ' + result['url']['registered_domain'])
    st.markdown('#### URL indicators')
    for indicator in result['url']['indicators']:
        st.text(indicator)
    if not result['url']['indicators']:
        st.write('No listed URL heuristic triggered.')
    st.caption(result['url']['note'])
    st.markdown('#### Historical phishing snapshot')
    st.text(result['history'])
    st.caption('Local historical lookup; no live threat intelligence or BigQuery request.')
    st.markdown('#### Job-content classifier')
    content = result['content']
    st.text(content['status'] + ': ' + content['reason'])
    if content['status'] == 'Analyzed':
        st.metric('Uncalibrated model score (0–1)', f"{content['score']:.3f}")
        st.text('Model: ' + content['version'] + ' | text source: ' + result['text_source'])
        st.text('Risk-associated terms present: ' + (', '.join(content['risk_terms']) or 'None among leading contributions'))
    st.caption('Policy: historical match or model score ≥0.5 → Elevated Risk; URL indicator → Some Warning Signals; missing usable text → Insufficient Evidence; otherwise No Strong Warning Signals.')
    st.warning('Advisory evidence only, not a definitive fraud determination. Independently verify the employer. No scan is saved to cloud storage.')
