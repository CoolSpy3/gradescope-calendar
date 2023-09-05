import json
import os.path
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from googleapiclient.discovery import build as buildGoogleAPIService

import utils

# Read in the config file
gradescope_token = None

with open('gradescope_secrets.json') as f:
    gradescope_token = json.load(f)['gradescope_token']

# Download the Gradescope assignments into a structure that looks like this:
# {
#     "Course Name": [
#         {
#             "name": "Assignment Name",
#             "due_date": {
#                 "normal": datetime,
#                 "late": datetime
#             },
#             "completed": bool
#         }
#     ]
# }
# The actual implementation of this is hacky nonsense because Gradescope doesn't have an API

# Get the list of courses
gradescope_courses = [
    (
        utils.transform_or_default(course.find("./h3"), lambda course_name: course_name.text, "<Unknown Course>").strip(),
        course.attrib["href"]
    )
    for course in utils.get_data_from_gradescope("", ".//div[@class='courseList']/div[@class='courseList--coursesForTerm'][2]/a[@class='courseBox']", gradescope_token)
]

# For each course, get the list of assignments
gradescope_assignments = {
    course_name: [
        {
            "name": utils.get_assignment_name(assignment),
            "due_date": utils.due_date_from_progress_div(assignment[2][0][2]),
            "completed": assignment[1][1].text == "Submitted"
        }
        for assignment in utils.get_data_from_gradescope(course_url, ".//table[@id='assignments-student-table']/tbody/tr", gradescope_token)
        if len(assignment[2][0]) > 1 # If the assignment is past due, Gradescope will not include a progress bar div
    ]
    for course_name, course_url in gradescope_courses
}
# Filter out assignments that don't have a due date or were parsed incorrectly
gradescope_assignments = {
    course_name: [
        assignment for assignment in course_assignments if isinstance(assignment, dict) and assignment["due_date"]["normal"]
    ]
    for course_name, course_assignments in gradescope_assignments.items()
}

# Connect to the Google Calendar API ( I tried to use Google Tasks, but they don't support color coding or (more importantly) due times (only dates) )
with buildGoogleAPIService('calendar', 'v3', credentials=utils.login_with_google()) as calendar_service:

    color_settings = None
    if os.path.exists("color_settings.json"):
        with open("color_settings.json") as f:
            color_settings = json.load(f)

    # Validate the user's color settings
    # If you want to save API calls (and you trust your config file), you can set validate_colors to False
    if not color_settings or not color_settings.get("validate_colors", True):
        colors = calendar_service.colors().get().execute()["event"]
        if not os.path.exists("colors.json"):
            with open("colors.json", "w") as f:
                json.dump(colors, f, indent=4)

        if not color_settings or not all(course_name in color_settings and color_settings[course_name] in colors for course_name, _ in gradescope_courses) or not color_settings.get("Completed", None):
            print("Please fill out color_settings.json with the colors you want to use for each course. The colors are listed in colors.json (the background color will show up). Match each course to a color id. Then run this script again.")
            if color_settings:
                invalid_settings = [course_name for course_name, _ in gradescope_courses if not (course_name in color_settings and color_settings[course_name] in colors)]
                if not color_settings.get("Completed", None):
                    invalid_settings.append("Completed")
                print(f"The following settings are currently missing or invalid: {invalid_settings}")
            else:
                with open("color_settings.json", "w") as f:
                    default_color_settings = { course_name: "" for course_name, _ in gradescope_courses }
                    default_color_settings["Completed"] = ""
                    json.dump(default_color_settings, f, indent=4)
            exit(1)

    gradescope_calendar_id = utils.find_gradescope_calendar_id(calendar_service) or utils.create_gradescope_calendar(calendar_service)

    calendar_events = list(utils.enumerate_calendar_events(calendar_service, gradescope_calendar_id))

    # Only send a single batch request to the Google Calendar API
    event_update_batch = calendar_service.new_batch_http_request()

    for course_name, course_url in gradescope_courses:
        for assignment in gradescope_assignments[course_name]:
            calendar_event = utils.get_assignment_in_calendar(assignment, calendar_events)

            if not calendar_event:
                if assignment["due_date"]["normal"] > datetime.now(timezone.utc):
                    utils.create_assignment_event(calendar_service, event_update_batch, gradescope_calendar_id, course_name, course_url, assignment, color_settings)
            elif assignment["completed"] and calendar_event["status"] != "cancelled":
                event_update_batch.add(calendar_service.events().patch(calendarId=gradescope_calendar_id, eventId=calendar_event["id"], body={"colorId": color_settings["Completed"]}))

    event_update_batch.execute()
