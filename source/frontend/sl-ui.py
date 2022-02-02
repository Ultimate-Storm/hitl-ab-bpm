import streamlit as st
import uploader
import dashboard


def setup():
    if 'new_proposal' not in st.session_state:
        st.session_state['new_proposal'] = False
    if 'data_open' not in st.session_state:
        st.session_state['data_open'] = False


def main():
    setup()
    st.set_page_config(page_title="HITL-AB-BPM", page_icon="🔁")
    st.title("HITL-AB-BPM Experiment-Cockpit")
    uploader.upload_files()
    dashboard.dashboard()

    # set_bapol()
    # experiment_cockpit()
    # display_results()
    # view_results()


if __name__ == '__main__':
    main()
