import time
import dropbox
import requests
import streamlit as st
import io
from openai import OpenAI


BASE_FOLDER = "/retirement-age"  # change per app
COUNTRY = "Finland"


# ===============================
# Get fresh Dropbox access token
# ===============================
def get_dropbox_access_token():
    r = requests.post(
        "https://api.dropboxapi.com/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": st.secrets["DROPBOX_REFRESH_TOKEN"],
            "client_id": st.secrets["DROPBOX_APP_KEY"],
            "client_secret": st.secrets["DROPBOX_APP_SECRET"],
        },
    )
    r.raise_for_status()
    return r.json()["access_token"]


# ===============================
# Helper: Dropbox client
# ===============================
def _get_dbx():
    token = get_dropbox_access_token()
    return dropbox.Dropbox(token)

# line changed in _get_dbx after switching to refresh token (dropbox_token):
# line changed in _get_dbx after switching to refresh token return dropbox.Dropbox(dropbox_token.strip())


# ===============================
# Create per-interview folder
# ===============================
def ensure_interview_folder(dbx, interview_id):
    # ensure parent folder exists
    try:
        dbx.files_create_folder(BASE_FOLDER)
    except dropbox.exceptions.ApiError:
        pass  # already exists

    # ensure country folder exists
    country_path = f"{BASE_FOLDER}/{COUNTRY}"
    try:
        dbx.files_create_folder(country_path)
    except dropbox.exceptions.ApiError:
        pass

    # create interview folder inside country
    folder_path = f"{country_path}/{interview_id}"
    try:
        dbx.files_create_folder(folder_path)
    except dropbox.exceptions.ApiError:
        pass

    return folder_path

# function changed in _get_dbx after switching to refresh token
# def ensure_interview_folder(dbx, interview_id):
#     folder_path = f"/interviews/{interview_id}" # line changed after switching to refresh token
#     try:
#         dbx.files_create_folder(folder_path) # line changed after switching to refresh token dbx.files_create_folder_v2(folder_path)
#     except dropbox.exceptions.ApiError as e:
#         # Ignore "already exists"
#         if not (
#             isinstance(e.error, dropbox.files.CreateFolderError)
#             and e.error.is_path()
#             and e.error.get_path().is_conflict()
#         ):
#             raise
#     return folder_path


# ===============================
# Save prompt
# ===============================
def save_prompt(dbx, folder_path, system_prompt):
    filename = f"{folder_path}/prompt.txt"
    dbx.files_upload(
        system_prompt.encode("utf-8"),
        filename,
        mode=dropbox.files.WriteMode.overwrite,
    )

# autorename above changed after switching to refresh token


# ===============================
# Save transcript
# ===============================
def save_transcript(dbx, folder_path, messages):
    content = "\n".join(
        f"{m['role']}: {m['content']}" for m in messages
    )
    filename = f"{folder_path}/transcript.txt"
    dbx.files_upload(
        content.encode("utf-8"),
        filename,
        mode=dropbox.files.WriteMode.overwrite,
    )


# ===============================
# Save timing metadata
# ===============================
def save_meta(dbx, folder_path, start_time):
    duration = (time.time() - start_time) / 60
    content = (
        f"Start time (UTC): {time.strftime('%d/%m/%Y %H:%M:%S', time.gmtime(start_time))}\n"
        f"Interview duration (minutes): {duration:.2f}"
    )
    filename = f"{folder_path}/meta.txt"
    dbx.files_upload(
        content.encode("utf-8"),
        filename,
        mode=dropbox.files.WriteMode.overwrite,
    )


# ===============================
# Final save — call ONCE
# ===============================
def finalize_interview_to_dropbox(
    interview_id,
    messages,
    system_prompt,
    start_time,
):
    dbx = _get_dbx()  # line changed after switching to refresh token _get_dbx(dropbox_token)
    folder = ensure_interview_folder(dbx, interview_id)

    save_prompt(dbx, folder, system_prompt)
    save_transcript(dbx, folder, messages)
    save_meta(dbx, folder, start_time)
# line removed in finalize_interview_to_dropbox after switching to refresh token dropbox_token,


def transcribe_audio(audio_bytes):
    client = OpenAI(api_key=st.secrets["API_KEY_OPENAI"])

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "response.wav"

    transcript = client.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe",
        file=audio_file,
    )

    return transcript.text.strip()
