from __future__ import annotations

from pathlib import Path

try:
    import streamlit as st
except Exception as exc:  # pragma: no cover - UI runtime guard
    raise SystemExit(
        "Streamlit is not installed. Run setup_ui.bat or: python -m pip install -r requirements-ui.txt"
    ) from exc

from ui import actions, components, readers

ROOT = Path(__file__).resolve().parents[1]


st.set_page_config(page_title="LivinClaw Dashboard", layout="wide")

st.title("LivinClaw — Local Alive Agent Dashboard")
st.caption("A local autonomous runtime with inbox/outbox, ticks, tasks, and persistent memory.")
st.warning(
    "The dashboard does not call the LLM directly. It sends messages through Inbox and processes them through the runtime tick."
)

if "current_draft_message" not in st.session_state:
    st.session_state["current_draft_message"] = ""
if "last_sent_message_id" not in st.session_state:
    st.session_state["last_sent_message_id"] = None
if "last_action_status" not in st.session_state:
    st.session_state["last_action_status"] = {"level": "info", "text": "Not available yet", "details": None}

chat_tab, runtime_tab, tasks_tab, memory_tab, io_tab, logs_tab, controls_tab = st.tabs(
    ["Chat", "Runtime", "Tasks", "Memory", "Inbox / Outbox", "Logs", "Controls"]
)

with chat_tab:
    rerun = getattr(st, "rerun", getattr(st, "experimental_rerun", None))
    st.subheader("LivinClaw Chat")
    st.caption(
        "Talk to the alive agent. Messages go through Inbox → Interactive Tick → Managed Context → Outbox."
    )

    runtime_snapshot = readers.read_runtime_snapshot(ROOT)
    components.render_chat_status_strip(st, runtime_snapshot)

    transcript_data = readers.read_chat_transcript(ROOT, limit=30)
    if transcript_data["error"]:
        st.warning(transcript_data["error"])
    if transcript_data["warning"]:
        st.warning(transcript_data["warning"])
    components.render_chat_transcript(st, transcript_data["messages"])

    status_info = st.session_state.get("last_action_status", {})
    status_level = status_info.get("level")
    status_text = status_info.get("text")
    if status_text:
        if status_level == "success":
            st.success(status_text)
        elif status_level == "warning":
            st.warning(status_text)
        elif status_level == "error":
            st.error(status_text)
        else:
            st.info(status_text)

    st.text_area(
        "Type your message",
        key="current_draft_message",
        height=90,
        placeholder="Message LivinClaw...",
        label_visibility="collapsed",
    )
    if st.button("Send message", type="primary"):
        ok, result = actions.send_message_and_run_tick(st.session_state["current_draft_message"], root=ROOT)
        st.session_state["last_sent_message_id"] = result.get("message_id")
        st.session_state["current_draft_message"] = ""
        st.session_state["last_action_status"] = {
            "level": "success" if ok else ("warning" if result.get("tick_ok") else "error"),
            "text": (
                "Message sent and response received."
                if result.get("response_found")
                else (
                    "No response generated for this turn yet."
                    if result.get("tick_ok")
                    else "Could not run interactive tick."
                )
            ),
            "details": result,
        }
        if rerun:
            rerun()

    with st.expander("Advanced"):
        if st.button("Queue without running tick"):
            ok, message = actions.append_user_message(st.session_state["current_draft_message"], root=ROOT)
            if ok:
                st.session_state["last_sent_message_id"] = message
                st.session_state["current_draft_message"] = ""
                st.session_state["last_action_status"] = {
                    "level": "warning",
                    "text": "Message queued, but the runtime did not produce a response.",
                    "details": {"message_id": message},
                }
                if rerun:
                    rerun()
            else:
                st.session_state["last_action_status"] = {"level": "error", "text": message, "details": None}
                if rerun:
                    rerun()

    with st.expander("Try examples"):
        st.markdown("- olá")
        st.markdown("- me explique sua arquitetura")
        st.markdown("- o que você lembra sobre este projeto?")
        st.markdown("- @status")
        st.markdown("- @task revisar memória")
        st.markdown("- @note prefiro respostas diretas")

    components.render_managed_context_panel(st, runtime_snapshot)

    details = st.session_state.get("last_action_status", {}).get("details")
    if details:
        with st.expander("Last action details"):
            st.json(details)

with runtime_tab:
    st.subheader("Runtime")
    runtime = readers.read_runtime_snapshot(ROOT)

    components.render_status_cards(
        st,
        {
            "Inbox pending": runtime["counts"]["inbox_pending"],
            "Inbox processed": runtime["counts"]["inbox_processed"],
            "Outbox messages": runtime["counts"]["outbox_total"],
            "Tasks pending": runtime["counts"]["tasks_pending"],
            "Tasks done": runtime["counts"]["tasks_completed"],
        },
    )

    st.markdown(f"**Provider:** {runtime['model_provider']}")
    st.markdown(f"**Model:** {runtime['model_name']}")
    st.markdown(f"**Base URL:** {runtime['base_url']}")
    st.markdown(f"**Last known tick log line:** `{runtime['last_tick_line']}`")

    for section, error in runtime["errors"].items():
        if error:
            st.warning(f"{section}: {error}")

with tasks_tab:
    st.subheader("Tasks")
    st.button("Refresh tasks")
    tasks = readers.read_tasks(ROOT)
    if tasks["error"]:
        st.warning(tasks["error"])

    components.render_task_lists(st, tasks["pending"], tasks["completed"], tasks["other"])
    components.render_file_preview(st, "Raw tasks.md preview", tasks["raw"])

with memory_tab:
    st.subheader("Memory")
    memory_index = readers.read_memory_index(ROOT)
    if not memory_index["exists"]:
        st.warning("No memory workspace found yet.")

    st.markdown("**Topic folders**")
    if memory_index["topics"]:
        selected_topic = st.selectbox("Select topic", options=memory_index["topics"])
        topic_data = readers.read_memory_topic(ROOT, selected_topic)
        if topic_data["error"]:
            st.warning(topic_data["error"])
        else:
            for item in topic_data["files"]:
                components.render_file_preview(st, item["name"], item["content"], height=180)
    else:
        st.info("Not available yet")

    st.markdown("**Legacy memory files**")
    if memory_index["legacy_files"]:
        selected_legacy = st.selectbox("Select legacy file", options=memory_index["legacy_files"])
        legacy = readers.read_legacy_memory_file(ROOT, selected_legacy)
        if legacy["error"]:
            st.warning(legacy["error"])
        else:
            components.render_file_preview(st, selected_legacy, legacy["content"], height=180)
    else:
        st.info("Not available yet")

with io_tab:
    st.subheader("Inbox / Outbox")
    io_data = readers.read_inbox_outbox(ROOT)

    for name in ("inbox", "outbox"):
        if io_data[name]["error"]:
            st.warning(f"{name}: {io_data[name]['error']}")
        if io_data[name]["warning"]:
            st.warning(f"{name}: {io_data[name]['warning']}")

    components.render_status_cards(
        st,
        {
            "Inbox pending": io_data["counts"]["inbox_pending"],
            "Inbox processed": io_data["counts"]["inbox_processed"],
            "Outbox total": io_data["counts"]["outbox_total"],
        },
    )

    col1, col2 = st.columns(2)
    with col1:
        components.render_message_cards(st, io_data["inbox"]["messages"], "Inbox messages")
        components.render_file_preview(st, "Inbox raw preview", io_data["inbox"]["raw"], height=180)
    with col2:
        components.render_message_cards(st, io_data["outbox"]["messages"], "Outbox messages")
        components.render_file_preview(st, "Outbox raw preview", io_data["outbox"]["raw"], height=180)

with logs_tab:
    st.subheader("Logs")
    st.button("Refresh logs")
    tail_lines = st.selectbox("Lines", options=[100, 500], index=0)
    filter_text = st.text_input("Filter text", value="")
    logs = readers.read_logs(ROOT, tail_lines=tail_lines, text_filter=filter_text)

    if logs["error"]:
        st.warning(logs["error"])
    st.code("\n".join(logs["lines"]) if logs["lines"] else "No logs yet.")

with controls_tab:
    st.subheader("Controls")
    st.caption("Only controls mapped to existing runtime entrypoints are enabled.")

    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Run Interactive Tick"):
        ok, msg = actions.run_interactive_tick(ROOT)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    if c2.button("Run Scheduled Tick"):
        ok, msg = actions.run_scheduled_tick(ROOT)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    c3.button("Run Maintenance Tick", disabled=True)
    c4.button("Run Recovery Tick", disabled=True)
