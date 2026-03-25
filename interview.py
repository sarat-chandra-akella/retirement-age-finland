import streamlit as st
import time
import uuid

from utils import finalize_interview_to_dropbox, transcribe_audio
import config


# =========================
# TIME LIMIT CONFIGURATION
# =========================
MAX_INTERVIEW_SECONDS = 7 * 60  # 7 minutes

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
    # 1. Add system prompt (NO images inside this)
    st.session_state.messages.append(
        {"role": "system", "content": config.SYSTEM_PROMPT}
    )

    # 2. Manually create first message (UI content, not sent to model)
    first_message = """
Hei, kiitos osallistumisesta kyselyyn! Ennen kuin aloitamme, kopioi ja liitä Qualtrics-tunnuksesi alla olevaan kenttään.

Haastattelun aikana voit joko nauhoittaa tai kirjoittaa vastauksesi. Nopeamman vastaamisen vuoksi suosittelemme nauhoittamista.

Klikkaa tätä painiketta tallentaaksesi:

Kun olet valmis, klikkaa tätä painiketta lähettääksesi vastauksesi:

Huom: tallennamme vain tekstimuotoiset transkriptiot. Vastaukset ovat anonyymejä.
"""

    # 3. Add to chat history as assistant message
    st.session_state.messages.append(
        {"role": "assistant", "content": first_message}
    )

# =========================
# Display transcript (single source of truth)
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

    if "audio_key" not in st.session_state:
        st.session_state.audio_key = 0

    # Input always at the bottom
    with st.container():
        audio = st.audio_input(
            "Tallenna vastauksesi",
            key=f"audio_{st.session_state.audio_key}"
        )
        text_fallback = st.chat_input("Tai kirjoita vastauksesi")

    user_msg = None

    if audio is not None:
        with st.spinner("Litterointi käynnissä..."):
            user_msg = transcribe_audio(audio.getvalue())

        st.markdown("**Litteroitu vastauksesi:**")
        st.markdown(user_msg)

    if user_msg is None:
        user_msg = text_fallback

    if user_msg:
        # =========================
        # Create interview_id from FIRST response
        # =========================
        if "interview_id" not in st.session_state:
            st.session_state.interview_id = f"{user_msg}_{uuid.uuid4().hex}"

        st.session_state.messages.append(
            {"role": "user", "content": user_msg}
        )

        with st.chat_message("user", avatar=config.AVATAR_RESPONDENT):
            st.markdown(user_msg)

        if time_exceeded:
            finalize_interview_to_dropbox(
                interview_id=st.session_state.interview_id,
                messages=st.session_state.messages,
                system_prompt=config.SYSTEM_PROMPT,
                start_time=st.session_state.start_time,
            )
            st.session_state.interview_active = False
            st.markdown("Haastattelu on päättynyt aikarajan vuoksi. Kiitos!")
            st.stop()

        response = client.chat.completions.create(
            model=config.MODEL,
            messages=st.session_state.messages,
            max_tokens=config.MAX_OUTPUT_TOKENS,
        )
        assistant_text_raw = response.choices[0].message.content
        assistant_text = assistant_text_raw.replace("x7y8", "").replace("TIME_EXCEEDED", "").strip()
        st.session_state.messages.append(
            {"role": "assistant", "content": assistant_text}
        )

        with st.chat_message("assistant", avatar=config.AVATAR_INTERVIEWER):
            st.markdown(assistant_text, unsafe_allow_html=True)

        # =========================
        # END INTERVIEW IF CODE FOUND
        # =========================
        if "x7y8" in assistant_text_raw:
            finalize_interview_to_dropbox(
                interview_id=st.session_state.interview_id,
                messages=st.session_state.messages,
                system_prompt=config.SYSTEM_PROMPT,
                start_time=st.session_state.start_time,
            )
            st.session_state.interview_active = False
            st.markdown(config.CLOSING_MESSAGES["x7y8"])
            st.stop()

        st.session_state.audio_key += 1
        st.rerun()