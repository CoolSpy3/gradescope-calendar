import os
from datetime import datetime

import requests
import tzlocal
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from lxml import etree as ElementTree

CALENDAR_DESCRIPTION = "<USE AS GRADESCOPE CALENDAR>"
GRADESCOPE_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S %z"

#region Google Calendar

def login_with_google():
    google_API_scopes = ['https://www.googleapis.com/auth/calendar']

    # Copied from Google's API documentation
    google_credentials = None
    if os.path.exists('google_token.json'):
        google_credentials = Credentials.from_authorized_user_file('google_token.json', google_API_scopes)

    # If there are no (valid) credentials available, let the user log in.
    if not google_credentials or not google_credentials.valid:
        if google_credentials and google_credentials.expired and google_credentials.refresh_token:
            try:
                google_credentials.refresh(Request())
            except RefreshError:
                google_credentials = None
        else:
            google_credentials = None

        if not google_credentials:
            oauthFlow = InstalledAppFlow.from_client_secrets_file('./google_secrets.json', scopes=google_API_scopes)
            google_credentials = oauthFlow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('google_token.json', 'w') as token:
            token.write(google_credentials.to_json())

    return google_credentials

def enumerate_calendar_events(calendar_service, calendar_id):
    page_token = None
    while True:
        events = calendar_service.events().list(calendarId=calendar_id, pageToken=page_token).execute()
        for event in events["items"]:
            yield event
        page_token = events.get("nextPageToken")
        if not page_token:
            break

#endregion

#region Gradescope

def format_gradescope_url(url):
    return f'https://www.gradescope.com{url if url.startswith("/") else f"/{url}"}'

def get_data_from_gradescope(url, query, gradescope_token):
    gradescope_cookies = { "signed_token": gradescope_token }
    with requests.get(format_gradescope_url(url), cookies=gradescope_cookies) as response:
        if response.status_code != 200:
            print(f"Gradescope Error: {response.status_code}!")
            print(response.content)
            exit(1)

        return ElementTree.HTML(response.content.decode(), None).findall(query)

def transform_or_default(data, transform, default):
    return default if data == None else transform(data)

#endregion

#region Calendar

def is_gradescope_calendar(calendar) -> bool:
    if calendar["accessRole"] != "owner" or calendar.get("deleted", False):
        return False
    return CALENDAR_DESCRIPTION in calendar.get("description", "")

def create_gradescope_calendar(calendar_service):
    calendar = {
        "summary": "Gradescope Assignments",
        "description": CALENDAR_DESCRIPTION,
        "timeZone": str(tzlocal.get_localzone())
    }
    created_calendar = calendar_service.calendars().insert(body=calendar).execute()
    return created_calendar["id"]

def find_gradescope_calendar_id(calendarService):
    page_token = None
    while True:
        calendar_list = calendarService.calendarList().list(pageToken=page_token).execute()
        for calendar_list_entry in calendar_list["items"]:
            if is_gradescope_calendar(calendar_list_entry):
                return calendar_list_entry["id"]
        page_token = calendar_list.get("nextPageToken")
        if not page_token:
            break

    return None

#endregion

#region Assignments

def get_assignment_in_calendar(assignment, calendar_events):
    for event in calendar_events:
        if event["summary"] == assignment["name"] and datetime.fromisoformat(event["start"]["dateTime"]) == assignment["due_date"]["normal"]: # and datetime.fromisoformat(event["end"]["dateTime"]) == assignment["due_date"]["late"]
            return event

    return None

def create_assignment_event(calendar_service, event_create_batch, gradescope_calendar_id, course_name, course_url, assignment, color_settings):
    event = {
        "summary": assignment["name"],
        "description": f'Assignment for <a href="{format_gradescope_url(course_url)}">{course_name}</a> on Gradescope',
        "start": {
            "dateTime": assignment["due_date"]["normal"].isoformat()
        },
        "end": {
            "dateTime": assignment["due_date"]["normal"].isoformat()
            # "dateTime": assignment["due_date"]["late"].isoformat()
        },
        "colorId": color_settings["Completed"] if assignment["completed"] else color_settings[course_name],
    }
    event_create_batch.add(calendar_service.events().insert(calendarId=gradescope_calendar_id, body=event))


def get_assignment_name(assignment):
    assignment_name = assignment.find("./th")
    return transform_or_default(assignment_name[0] if len(assignment_name) > 0 else assignment_name, lambda assignment_name: assignment_name.text, "<Unknown Assignment>").strip()

def due_date_from_progress_div(progress_div):
    times = progress_div.findall("./time")
    return {
        "normal": datetime.strptime(times[1].get("datetime"), GRADESCOPE_DATETIME_FORMAT),
        "late": datetime.strptime(times[2].get("datetime"), GRADESCOPE_DATETIME_FORMAT) if len(times) > 2 else None
    }

#endregion
