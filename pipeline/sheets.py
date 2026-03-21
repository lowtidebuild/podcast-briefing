"""Google Sheets integration — episode management dashboard."""

import json
import os
import gspread
from google.oauth2.service_account import Credentials


HEADER_ROW = [
    "Date", "Podcast", "Title", "Guest", "Category",
    "⭐", "✔읽음", "Episode Link", "Transcript",
    "한글요약", "Notes",
]

REPO_OWNER = "lowtidebuild"
REPO_NAME = "podcast-briefing"


def get_sheet():
    """Connect to the Google Sheet. Returns None if not configured."""
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")

    if not creds_json or not sheet_id:
        return None

    creds = Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).sheet1


def append_episode(episode, summary, slug):
    """Add an episode row to the Google Sheet.

    Silently skips if Sheets is not configured.
    """
    try:
        sheet = get_sheet()
        if not sheet:
            print("    Google Sheets not configured, skipping")
            return

        # Create header row if sheet is empty
        if not sheet.row_values(1):
            sheet.append_row(HEADER_ROW)

        # Guest info
        guest_name = ""
        guest = summary.get("guest")
        if guest and isinstance(guest, dict):
            name = guest.get("name", "")
            title = guest.get("title", "")
            guest_name = f"{name} — {title}" if title else name

        # Transcript link (GitHub raw URL for easy reading)
        transcript_url = (
            f"https://github.com/{REPO_OWNER}/{REPO_NAME}"
            f"/blob/main/data/transcripts/{slug}.txt"
        )

        # Korean summary preview (first 200 chars)
        summary_ko = summary.get("summary_ko", "")
        summary_preview = summary_ko[:200] + ("..." if len(summary_ko) > 200 else "")

        sheet.append_row([
            episode["published"][:10],       # Date
            episode["podcast"],              # Podcast
            episode["title"],                # Title
            guest_name,                      # Guest
            episode["category"],             # Category
            "",                              # ⭐ (user-editable)
            "",                              # ✔읽음 (user-editable)
            episode.get("link", ""),         # Episode Link
            transcript_url,                  # Transcript
            summary_preview,                 # 한글요약
            "",                              # Notes (user-editable)
        ])
        print("    Added to Google Sheet")

    except Exception as e:
        print(f"    Google Sheets error (non-fatal): {e}")
