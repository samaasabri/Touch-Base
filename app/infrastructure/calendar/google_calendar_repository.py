from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import Settings
from app.domain.ports.calendar_repository import CalendarRepository

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarRepository(CalendarRepository):
    def __init__(self, settings: Settings):
        self.settings = settings

    def _parse_datetime(self, datetime_str: str):
        formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %I:%M %p",
            "%Y-%m-%d",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y",
            "%B %d, %Y %H:%M",
            "%B %d, %Y %I:%M %p",
            "%B %d, %Y",
        ]
        for fmt in formats:
            try:
                return datetime.datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue
        return None

    def _format_event_time(self, event_time: dict) -> str:
        if "dateTime" in event_time:
            dt = datetime.datetime.fromisoformat(event_time["dateTime"].replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %I:%M %p")
        if "date" in event_time:
            return f"{event_time['date']} (All day)"
        return "Unknown time format"

    def _get_timezone(self, service) -> str:
        timezone_id = self.settings.timezone_fallback
        try:
            settings = service.settings().list().execute()
            for setting in settings.get("items", []):
                if setting.get("id") == "timezone":
                    timezone_id = setting.get("value")
                    break
        except Exception:
            pass
        return timezone_id

    def _get_calendar_service(self):
        creds = None
        token_path: Path = self.settings.calendar_token_path
        credentials_path: Path = self.settings.credentials_path

        if token_path.exists():
            creds = Credentials.from_authorized_user_info(
                json.loads(token_path.read_text(encoding="utf-8")), SCOPES
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not credentials_path.exists():
                    return None
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")

        return build("calendar", "v3", credentials=creds)

    def list_events(self, start_date: str, days: int) -> dict:
        try:
            service = self._get_calendar_service()
            if not service:
                return {"status": "error", "message": "Failed calendar authentication.", "events": []}
            start_time = datetime.datetime.utcnow()
            if start_date and start_date.strip():
                try:
                    start_time = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                except ValueError:
                    return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD.", "events": []}
            days = days if days and days > 0 else 1
            end_time = start_time + datetime.timedelta(days=days)
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=f"{start_time.isoformat()}Z",
                    timeMax=f"{end_time.isoformat()}Z",
                    maxResults=100,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
            if not events:
                return {"status": "success", "message": "No upcoming events found.", "events": []}
            formatted = []
            for event in events:
                formatted.append(
                    {
                        "id": event.get("id"),
                        "summary": event.get("summary", "Untitled Event"),
                        "start": self._format_event_time(event.get("start", {})),
                        "end": self._format_event_time(event.get("end", {})),
                        "location": event.get("location", ""),
                        "description": event.get("description", ""),
                        "attendees": [a.get("email") for a in event.get("attendees", []) if "email" in a],
                        "link": event.get("htmlLink", ""),
                    }
                )
            return {"status": "success", "message": f"Found {len(formatted)} event(s).", "events": formatted}
        except Exception as e:
            return {"status": "error", "message": f"Error fetching events: {e}", "events": []}

    def create_event(
        self, summary: str, start_time: str, end_time: str, attendees: Optional[list[str]] = None
    ) -> dict:
        try:
            service = self._get_calendar_service()
            if not service:
                return {"status": "error", "message": "Failed calendar authentication."}
            start_dt = self._parse_datetime(start_time)
            end_dt = self._parse_datetime(end_time)
            if not start_dt or not end_dt:
                return {"status": "error", "message": "Invalid date/time format. Use YYYY-MM-DD HH:MM."}
            timezone_id = self._get_timezone(service)
            body = {
                "summary": summary,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone_id},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone_id},
            }
            if attendees:
                body["attendees"] = [{"email": email} for email in attendees]
            event = (
                service.events()
                .insert(calendarId="primary", body=body, sendUpdates="all")
                .execute()
            )
            attendee_list = ", ".join(attendees) if attendees else "none"
            return {
                "status": "success",
                "message": f"Event '{summary}' created and invitations sent to: {attendee_list}",
                "event_id": event["id"],
                "event_link": event.get("htmlLink", ""),
            }
        except Exception as e:
            return {"status": "error", "message": f"Error creating event: {e}"}

    def edit_event(self, event_id: str, summary: str, start_time: str, end_time: str) -> dict:
        try:
            service = self._get_calendar_service()
            if not service:
                return {"status": "error", "message": "Failed calendar authentication."}
            try:
                event = service.events().get(calendarId="primary", eventId=event_id).execute()
            except Exception:
                return {"status": "error", "message": f"Event with ID {event_id} not found in primary calendar."}
            if summary:
                event["summary"] = summary
            timezone_id = event.get("start", {}).get("timeZone", self.settings.timezone_fallback)
            if start_time:
                start_dt = self._parse_datetime(start_time)
                if not start_dt:
                    return {"status": "error", "message": "Invalid start time format. Use YYYY-MM-DD HH:MM."}
                event["start"] = {"dateTime": start_dt.isoformat(), "timeZone": timezone_id}
            if end_time:
                end_dt = self._parse_datetime(end_time)
                if not end_dt:
                    return {"status": "error", "message": "Invalid end time format. Use YYYY-MM-DD HH:MM."}
                event["end"] = {"dateTime": end_dt.isoformat(), "timeZone": timezone_id}
            updated_event = service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
            return {
                "status": "success",
                "message": "Event updated successfully",
                "event_id": updated_event["id"],
                "event_link": updated_event.get("htmlLink", ""),
            }
        except Exception as e:
            return {"status": "error", "message": f"Error updating event: {e}"}

    def delete_event(self, event_id: str, confirm: bool) -> dict:
        if not confirm:
            return {"status": "error", "message": "Please confirm deletion by setting confirm=True"}
        try:
            service = self._get_calendar_service()
            if not service:
                return {"status": "error", "message": "Failed calendar authentication."}
            service.events().delete(calendarId="primary", eventId=event_id).execute()
            return {
                "status": "success",
                "message": f"Event {event_id} has been deleted successfully",
                "event_id": event_id,
            }
        except Exception as e:
            return {"status": "error", "message": f"Error deleting event: {e}"}

    def find_free_time(
        self, date: str, duration_minutes: int = 15, emails: Optional[list[str]] = None
    ) -> list:
        emails = emails or []
        service = self._get_calendar_service()
        if not service:
            return []
        timezone_id = self._get_timezone(service)
        tz = ZoneInfo(timezone_id)
        day = datetime.datetime.strptime(date, "%Y-%m-%d")
        work_start = datetime.datetime(day.year, day.month, day.day, 9, 0, tzinfo=tz)
        work_end = datetime.datetime(day.year, day.month, day.day, 17, 0, tzinfo=tz)
        items = [{"id": "primary"}] + [{"id": email} for email in emails]
        try:
            fb = (
                service.freebusy()
                .query(
                    body={
                        "timeMin": work_start.isoformat(),
                        "timeMax": work_end.isoformat(),
                        "items": items,
                    }
                )
                .execute()
            )
        except Exception:
            return []
        busy = []
        for cal_data in fb.get("calendars", {}).values():
            for interval in cal_data.get("busy", []):
                busy.append(
                    (
                        datetime.datetime.fromisoformat(interval["start"]),
                        datetime.datetime.fromisoformat(interval["end"]),
                    )
                )
        busy.sort(key=lambda x: x[0])
        merged = []
        for start, end in busy:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        free = []
        cursor = work_start
        duration = datetime.timedelta(minutes=duration_minutes)
        for b_start, b_end in merged:
            if b_start > cursor and (b_start - cursor) >= duration:
                free.append({"start": cursor.isoformat(), "end": b_start.isoformat()})
            if b_end > cursor:
                cursor = b_end
        if cursor < work_end and (work_end - cursor) >= duration:
            free.append({"start": cursor.isoformat(), "end": work_end.isoformat()})
        return free
