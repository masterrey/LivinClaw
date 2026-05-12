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
st.info("Type a message and click 'Queue Message' or 'Send + Interactive Tick'.")
st.warning(
    "The dashboard does not call the LLM directly. It sends messages through Inbox and processes them through the runtime tick."
)

if "chat_input" not in st.session_state:
    st.session_state["chat_input"] = ""
if "latest_response" not in st.session_state:
    st.session_state["latest_response"] = ""
if "latest_response_notice" not in st.session_state:
    st.session_state["latest_response_notice"] = "Not available yet"

chat_tab, runtime_tab, tasks_tab, memory_tab, io_tab, logs_tab, controls_tab = st.tabs(
    ["Chat", "Runtime", "Tasks", "Memory", "Inbox / Outbox", "Logs", "Controls"]
)

with chat_tab:
    st.subheader("Chat")
    st.caption(
        "Examples: `olá` · `@status` · `@ask me explique sua arquitetura`"
        " · `@task revisar memória` · `@note prefiro respostas curtas`"
    )
    st.text_area("Message", key="chat_input", height=120)
    send_col, send_tick_col = st.columns(2)

    if send_col.button("Queue Message"):
        ok, message = actions.append_user_message(st.session_state["chat_input"], root=ROOT)
        if ok:
            st.success(f"Message queued in Inbox ({message}).")
        else:
            st.error(message)

    if send_tick_col.button("Send + Interactive Tick"):
        latest_before, latest_before_error = actions.read_latest_outbox_message(root=ROOT)
        if latest_before_error:
            st.error(latest_before_error)
        previous_latest_id = latest_before.id if latest_before else None
        st.session_state["latest_response"] = ""
        st.session_state["latest_response_notice"] = "Not available yet"

        ok, message = actions.append_user_message(st.session_state["chat_input"], root=ROOT)
        if not ok:
            st.error(message)
        else:
            tick_ok, tick_message = actions.run_interactive_tick(root=ROOT)
            if not tick_ok:
                st.error(f"Interactive tick failed: {tick_message}")
            else:
                latest, has_new_response, error = actions.read_new_outbox_response(
                    previous_message_id=previous_latest_id,
                    root=ROOT,
                )
                if error:
                    st.error(error)
                elif not has_new_response:
                    st.session_state["latest_response_notice"] = "No new response generated for this turn."
                    st.success("Interactive tick executed.")
                else:
                    st.session_state["latest_response"] = latest
                    st.session_state["latest_response_notice"] = ""
                    st.success("Interactive tick executed.")

    st.subheader("Latest response")
    latest = st.session_state.get("latest_response", "")
    if latest:
        st.write(latest)
    else:
        st.info(st.session_state.get("latest_response_notice", "Not available yet"))

    io_data = readers.read_inbox_outbox(ROOT)
    if io_data["inbox"]["warning"]:
        st.warning(io_data["inbox"]["warning"])
    if io_data["outbox"]["warning"]:
        st.warning(io_data["outbox"]["warning"])

    recent_col1, recent_col2 = st.columns(2)
    with recent_col1:
        components.render_message_cards(st, io_data["inbox"]["messages"], "Recent inbox messages")
    with recent_col2:
        components.render_message_cards(st, io_data["outbox"]["messages"], "Recent outbox messages")

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
