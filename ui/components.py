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
