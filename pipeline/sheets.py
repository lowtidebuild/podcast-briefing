"""Google Sheets integration — episode management dashboard."""

import json
import os
import gspread
from dataclasses import dataclass
from google.oauth2.service_account import Credentials

from quality import summary_text_errors


HEADER_ROW = [
    "Date", "Podcast", "Title", "Guest", "Category",
    "⭐", "✔읽음", "Episode Link", "Transcript",
    "Summary (EN)", "한글요약", "Notes",
]

REPO_OWNER = "lowtidebuild"
REPO_NAME = "podcast-briefing"


@dataclass
class SheetsAppendResult:
    ok: bool
    configured: bool
    error: str | None = None


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
            return SheetsAppendResult(ok=True, configured=False)

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

        # Full summaries
        summary_en = summary.get("summary_en", "")
        summary_ko = summary.get("summary_ko", "")

        # Detect summary failure. Keep this aligned with pipeline/quality.py.
        text_errors = summary_text_errors(summary, min_chars=50)
        if text_errors:
            status = "⚠️ SUMMARY FAILED"
            notes = "; ".join(text_errors)
        else:
            status = ""
            notes = ""

        sheet.append_row([
            episode["published"][:10],       # Date
            episode["podcast"],              # Podcast
            episode["title"],                # Title
            guest_name,                      # Guest
            episode["category"],             # Category
            status,                          # ⭐ (or ⚠️ SUMMARY FAILED)
            "",                              # ✔읽음 (user-editable)
            episode.get("link", ""),         # Episode Link
            transcript_url,                  # Transcript
            summary_en,                      # Summary (EN) (전문)
            summary_ko,                      # 한글요약 (전문)
            notes,                           # Notes (error detail or user-editable)
        ])
        if status:
            print(f"    ⚠️ Added to Google Sheet with SUMMARY FAILED flag")
        else:
            print("    Added to Google Sheet")
        return SheetsAppendResult(ok=True, configured=True)

    except Exception as e:
        print(f"    Google Sheets error (non-fatal): {e}")
        return SheetsAppendResult(ok=False, configured=True, error=str(e))
