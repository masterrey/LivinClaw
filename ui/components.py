from __future__ import annotations

from typing import Iterable


def render_status_cards(st, cards: dict[str, str | int]) -> None:
    columns = st.columns(len(cards)) if cards else []
    for index, (label, value) in enumerate(cards.items()):
        columns[index].metric(label, value)


def render_message_cards(st, messages: Iterable, title: str, limit: int = 8) -> None:
    st.subheader(title)
    listed = list(messages)[-limit:]
    if not listed:
        st.info("Not available yet")
        return

    for msg in reversed(listed):
        header = f"{msg.id} | {msg.sender} | {msg.source} | {msg.status}"
        with st.expander(header):
            st.caption(f"created_at: {msg.created_at}")
            if msg.processed_at:
                st.caption(f"processed_at: {msg.processed_at}")
            st.write(msg.content)


def render_task_lists(st, pending: list[str], completed: list[str], other: list[str]) -> None:
    left, right = st.columns(2)
    with left:
        st.subheader("Pending")
        if pending:
            for task in pending:
                st.markdown(f"- ⏳ {task}")
        else:
            st.info("Not available yet")
    with right:
        st.subheader("Done")
        if completed:
            for task in completed:
                st.markdown(f"- ✅ {task}")
        else:
            st.info("Not available yet")

    st.subheader("Other")
    if other:
        for line in other:
            st.markdown(f"- ℹ️ {line}")
    else:
        st.caption("No other task lines.")


def render_file_preview(st, title: str, content: str, height: int = 220) -> None:
    st.subheader(title)
    st.text_area(title, value=content, height=height, disabled=True, label_visibility="collapsed")


def render_chat_status_strip(st, runtime_snapshot: dict) -> None:
    counts = runtime_snapshot.get("counts", {})
    model_provider = runtime_snapshot.get("model_provider", "Unknown")
    model_name = runtime_snapshot.get("model_name", "Unknown")
    model_label = f"{model_provider}/{model_name}" if model_provider != "Unknown" else model_name
    errors = runtime_snapshot.get("errors", {})
    runtime_ready = not any(errors.get(name) for name in ("config", "inbox", "outbox"))

    render_status_cards(
        st,
        {
            "Alive runtime": "ready" if runtime_ready else "not ready",
            "Model": model_label or "Not available yet",
            "Pending tasks": counts.get("tasks_pending", "Not available yet"),
            "Inbox pending": counts.get("inbox_pending", "Not available yet"),
        },
    )


def render_chat_transcript(st, transcript: list[dict]) -> None:
    if not transcript:
        st.info("Not available yet")
        return

    for item in transcript:
        role = item.get("role", "assistant")
        content = item.get("content", "")
        if hasattr(st, "chat_message"):
            with st.chat_message("user" if role == "user" else "assistant"):
                st.write(content)
                with st.expander("Message details"):
                    st.caption(f"message_id: {item.get('message_id', 'unknown')}")
                    st.caption(f"status: {item.get('status', 'unknown')}")
                    st.caption(f"created_at: {item.get('created_at', 'unknown')}")
        else:
            title = "You" if role == "user" else "LivinClaw"
            with st.container():
                st.markdown(f"**{title}**")
                st.write(content)
                with st.expander("Message details"):
                    st.caption(f"message_id: {item.get('message_id', 'unknown')}")
                    st.caption(f"status: {item.get('status', 'unknown')}")
                    st.caption(f"created_at: {item.get('created_at', 'unknown')}")


def render_managed_context_panel(st, runtime_snapshot: dict) -> None:
    with st.expander("Managed Context", expanded=False):
        st.caption(
            "This chat uses the same runtime memory and context management as the alive agent. "
            "It is not a direct UI-to-LLM chat."
        )
        st.markdown("- Short memory: active")
        st.markdown("- Routed memory: bounded")
        st.markdown("- Pending tasks: included")
        st.markdown("- Tool policy: guarded")
        st.markdown("- Direct UI-to-LLM: disabled")
