import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from googleapiclient.discovery import build as buildGoogleAPIService

import utils

# Read in the config file
gradescope_token = None

with open('gradescope_secrets.json') as f:
    gradescope_token = json.load(f)['gradescope_token']

gradescope_courses = [
    (
        utils.transform_or_default(course.find("./h3"), lambda course_name: course_name.text, "<Unknown Course>").strip(),
        course.attrib["href"]
    )
    for course in utils.get_data_from_gradescope("", ".//div[@class='courseList']/div[@class='courseList--coursesForTerm'][2]/a[@class='courseBox']", gradescope_token)
]
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
gradescope_assignments = {
    course_name: [
        assignment for assignment in course_assignments if isinstance(assignment, dict) and assignment["due_date"]["normal"]
    ]
    for course_name, course_assignments in gradescope_assignments.items()
}

with buildGoogleAPIService('tasks', 'v1', credentials=utils.login_with_google()) as task_service:
    gradescope_tasklist_id = utils.find_gradescope_tasklist_id(task_service) or utils.create_gradescope_tasklist(task_service)

    tasks = list(utils.enumerate_tasks(task_service, gradescope_tasklist_id))

    task_create_batch = task_service.new_batch_http_request()

    for course_name, course_url in gradescope_courses:
        for assignment in gradescope_assignments[course_name]:
            task = utils.get_task_in_tasklist(assignment, tasks)

            if not task:
                if assignment["due_date"]["normal"] > datetime.now(timezone.utc):
                    utils.create_assignment_task(task_service, task_create_batch, gradescope_tasklist_id, course_name, course_url, assignment)
            elif assignment["completed"] and "completed" not in task:
                task_create_batch.add(task_service.tasks().patch(tasklist=gradescope_tasklist_id, task=task["id"], body={"status": "completed"}))

    task_create_batch.execute()
