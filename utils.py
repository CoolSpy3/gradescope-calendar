import os
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timezone

import requests
import tzlocal
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

TASKLIST_NAME = "Gradescope Assignments"
GRADESCOPE_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S %z"

#region Google Calendar

def login_with_google():
    google_API_scopes = ['https://www.googleapis.com/auth/tasks']

    # Copied from Google's API documentation
    google_credentials = None
    if os.path.exists('google_token.json'):
        google_credentials = Credentials.from_authorized_user_file('google_token.json', google_API_scopes)

    # If there are no (valid) credentials available, let the user log in.
    if not google_credentials or not google_credentials.valid:
        if google_credentials and google_credentials.expired and google_credentials.refresh_token:
            google_credentials.refresh(Request())
        else:
            oauthFlow = InstalledAppFlow.from_client_secrets_file('./google_secrets.json', scopes=google_API_scopes)
            google_credentials = oauthFlow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('google_token.json', 'w') as token:
            token.write(google_credentials.to_json())

    return google_credentials

def enumerate_tasks(task_service, tasklist_id):
    page_token = None
    while True:
        tasks = task_service.tasks().list(tasklist=tasklist_id, pageToken=page_token, showCompleted=True, showHidden=True).execute()
        for task in tasks["items"]:
            yield task
        page_token = tasks.get("nextPageToken")
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
            print("Gradescope Error!")
            print(response.content)
            exit(1)

        return ElementTree.fromstring(response.content).findall(query)

def transform_or_default(data, transform, default):
    return default if data == None else transform(data)

#endregion

#region Calendar

def is_gradescope_tasklist(tasklist) -> bool:
    return tasklist["title"] == TASKLIST_NAME

def create_gradescope_tasklist(task_service):
    task = {
        "title": TASKLIST_NAME
    }
    created_tasklist = task_service.tasklists().insert(body=task).execute()
    return created_tasklist["id"]

def find_gradescope_tasklist_id(task_service):
    page_token = None
    while True:
        tasklist = task_service.tasklists().list(pageToken=page_token).execute()
        for tasklist in tasklist["items"]:
            if is_gradescope_tasklist(tasklist):
                return tasklist["id"]
        page_token = tasklist.get("nextPageToken")
        if not page_token:
            break

    return None

#endregion

#region Assignments

def get_task_in_tasklist(assignment, tasks):
    for task in tasks:
        if task["title"] == assignment["name"] and datetime.fromisoformat(task["due"]) == assignment["due_date"]["normal"]:
            return task

    return None

def create_assignment_task(task_service, task_create_batch, gradescope_tasklist_id, course_name, course_url, assignment):
    task = {
        "title": assignment["name"],
        "notes": f'Assignment for <a href="{format_gradescope_url(course_url)}">{course_name}</a> on Gradescope',
        "due": assignment["due_date"]["normal"].isoformat(),
        "status": "completed" if assignment["completed"] else "needsAction"
    }

    task_create_batch.add(task_service.tasks().insert(tasklist=gradescope_tasklist_id, body=task))

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
