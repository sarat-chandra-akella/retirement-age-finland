import streamlit as st
import time
import uuid

from utils import finalize_interview_to_dropbox, transcribe_audio
import config

# =========================
# TIME LIMIT CONFIGURATION
# =========================
MAX_INTERVIEW_SECONDS = 8 * 60  # 8 minutes

# =========================
# Load API library
# =========================
if "gpt" in config.MODEL.lower():
    from openai import OpenAI
    api = "openai"
elif "claude" in config.MODEL.lower():
    import anthropic
    api = "anthropic"
else:
    raise ValueError("Unsupported model")

# =========================
# Page config
# =========================
st.set_page_config(
    page_title="Haastattelu",
    page_icon=config.AVATAR_INTERVIEWER,
)

# =========================
# Login handling
# =========================
if config.LOGINS:
    pwd_correct, username = check_password()
    if not pwd_correct:
        st.stop()
    st.session_state.username = username
else:
    st.session_state.username = "QID"

# =========================
# START INTERVIEW GATE
# =========================
if "started" not in st.session_state:
    st.session_state.started = False

if not st.session_state.started:
    if st.button("Aloita haastattelu"):
        st.session_state.started = True
    else:
        st.stop()

# =========================
# Session state init
# =========================
if "messages" not in st.session_state:
    st.session_state.messages = []

if "interview_active" not in st.session_state:
    st.session_state.interview_active = True

if "start_time" not in st.session_state:
    st.session_state.start_time = time.time()

if "in_part_v" not in st.session_state:
    st.session_state.in_part_v = False

# =========================
# Load API client
# =========================
if api == "openai":
    client = OpenAI(api_key=st.secrets["API_KEY_OPENAI"])
else:
    client = anthropic.Anthropic(api_key=st.secrets["API_KEY_ANTHROPIC"])

# =========================
# First interviewer message
# =========================
if not st.session_state.messages:
    st.session_state.messages.append(
        {"role": "system", "content": config.SYSTEM_PROMPT}
    )

    first_message = """Hei, kiitos osallistumisestasi tähän haastatteluun! Haastattelun aikana voit vastata joko **nauhoittamalla ääntä tai kirjoittamalla vastauksesi**. Nopeamman vastaamisen vuoksi suosittelemme äänen tallentamista.

Klikkaa tätä painiketta aloittaaksesi vastauksen nauhoittamisen:
<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAATCAYAAACgADyUAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAFESURBVDhP1ZTdS8JQGMafiZEXaTMlm5mzbNo/EFIQ9adLN0JZF1pQWuBH0MpgsbWGH9tp52Wato3ArvqNw/uc5+zZYezdEd71T4YliHjVh64bNMII3PH+roV2+5G0ohRRPiiRnse342DwNgtxuObeT3xBTdM89U2QF/qOv/Hfgo3GDer1azJiqzGq80y9+uUVms1b0hQcj8dQn18wHA6Rl3eQSm3QIodr7lmWBVV9xWQyIZ+CkrRFk3brgerRcQXlskKDa07LW8tmJaqzoCiuo9Pp0Q2O40Ap7dOwbZs6qd97QjqdQiazScFZy41GI9RqFzDc/hQiAuLxNTCHwTRN90EMyaSISuUQ0ZXoYpDDGEO320PX3dkwPshLJOLYK+4il9um+ZTQ36paPYfgXqdnJ56zyN++YxCFggy5kPdmfpY8AYAvP+KLLm+c9U4AAAAASUVORK5CYII=" width="20">

Kun olet valmis, klikkaa tätä painiketta lähettääksesi vastauksesi:
<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAZklEQVR4nGNgoBAw4pK4w8DwH5mvgkMthiC6RnSAbhATKZqxqWHCJUGsISzYFEh+/YpV43NubgwxJlJtR3cFEyGFhMAgMQBXIsEHYHqwxgK20MbrAlJdgayWCZcEMZoZGKiQmSgGAAYRFhubxjHdAAAAAElFTkSuQmCC" width="20">

Huomaa, että tallennamme vain tämän keskustelun tekstimuotoiset litteroinnit. Vastaamisesi on anonyymi, koska se liitetään vain tunnisteeseen, jonka annat nyt.

**Aloittaaksesi kirjoita Qualtricsista saamasi 7-numeroinen Chat ID alla olevaan kenttään.**

"""
    st.session_state.messages.append(
        {"role": "assistant", "content": first_message}
    )

# =========================
# Display transcript
# =========================
for m in st.session_state.messages[1:]:
    avatar = (
        config.AVATAR_INTERVIEWER
        if m["role"] == "assistant"
        else config.AVATAR_RESPONDENT
    )
    with st.chat_message(m["role"], avatar=avatar):
        st.markdown(m["content"], unsafe_allow_html=True)

# =========================
# MAIN CHAT LOOP
# =========================
if st.session_state.interview_active:

    elapsed = time.time() - st.session_state.start_time
    time_exceeded = elapsed >= MAX_INTERVIEW_SECONDS

    with st.container():
        user_msg = st.chat_input("Tai kirjoita vastauksesi")

    if time_exceeded and not st.session_state.in_part_v:
        st.session_state.messages.append({
            "role": "system",
            "content": "Haastatteluun varattu aika on päättynyt. Sinun tulee nyt siirtyä suoraan osaan V ja noudattaa näitä ohjeita täsmällisesti."
        })
        st.session_state.in_part_v = True

    if user_msg:
        if "interview_id" not in st.session_state:
            st.session_state.interview_id = f"{user_msg}_{uuid.uuid4().hex}"

        st.session_state.messages.append({"role": "user", "content": user_msg})

        with st.chat_message("user", avatar=config.AVATAR_RESPONDENT):
            st.markdown(user_msg)

        response = client.chat.completions.create(
            model=config.MODEL,
            messages=st.session_state.messages,
            max_tokens=config.MAX_OUTPUT_TOKENS,
        )

        assistant_text_raw = response.choices[0].message.content

        if "x7y8" in assistant_text_raw:
            st.session_state.messages.append({"role": "assistant", "content": "x7y8"})
        if "26mn" in assistant_text_raw:
            st.session_state.messages.append({"role": "assistant", "content": "26mn"})
        if "5j3k" in assistant_text_raw:
            st.session_state.messages.append({"role": "assistant", "content": "5j3k"})
        if "ab41" in assistant_text_raw:
            st.session_state.messages.append({"role": "assistant", "content": "ab41"})

        assistant_text = assistant_text_raw.replace("x7y8", "").replace("5j3k", "").replace("26mn", "").replace("ab41", "").strip()

        if assistant_text:
            st.session_state.messages.append({"role": "assistant", "content": assistant_text})

            with st.chat_message("assistant", avatar=config.AVATAR_INTERVIEWER):
                st.markdown(assistant_text, unsafe_allow_html=True)

        if "x7y8" in assistant_text_raw:
            st.session_state.messages.append({"role": "assistant", "content": config.CLOSING_MESSAGES["x7y8"]})
            finalize_interview_to_dropbox(
                interview_id=st.session_state.interview_id,
                messages=st.session_state.messages,
                system_prompt=config.SYSTEM_PROMPT,
                start_time=st.session_state.start_time,
            )
            st.session_state.interview_active = False
            st.markdown(config.CLOSING_MESSAGES["x7y8"])
            st.stop()

        if "5j3k" in assistant_text_raw:
            st.session_state.messages.append({"role": "assistant", "content": config.CLOSING_MESSAGES["5j3k"]})
            finalize_interview_to_dropbox(
                interview_id=st.session_state.interview_id,
                messages=st.session_state.messages,
                system_prompt=config.SYSTEM_PROMPT,
                start_time=st.session_state.start_time,
            )
            st.session_state.interview_active = False
            st.markdown(config.CLOSING_MESSAGES["5j3k"])
            st.stop()

        if "ab41" in assistant_text_raw:
            st.session_state.messages.append({"role": "assistant", "content": config.CLOSING_MESSAGES["ab41"]})
            finalize_interview_to_dropbox(
                interview_id=st.session_state.interview_id,
                messages=st.session_state.messages,
                system_prompt=config.SYSTEM_PROMPT,
                start_time=st.session_state.start_time,
            )
            st.session_state.interview_active = False
            st.markdown(config.CLOSING_MESSAGES["ab41"])
            st.stop()

        if "26mn" in assistant_text_raw:
            st.session_state.messages.append({"role": "assistant", "content": config.CLOSING_MESSAGES["26mn"]})
            finalize_interview_to_dropbox(
                interview_id=st.session_state.interview_id,
                messages=st.session_state.messages,
                system_prompt=config.SYSTEM_PROMPT,
                start_time=st.session_state.start_time,
            )
            st.session_state.interview_active = False
            st.markdown(config.CLOSING_MESSAGES["26mn"])
            st.stop()

        st.rerun()