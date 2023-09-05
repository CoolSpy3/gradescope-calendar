# Gradescope-Calendar
This project is a short script which downloads students' assignment due dates from Gradescope and adds them to their Google Calendar. There are a few alternative versions out there, but this one has a few benefits:
* It reads in credentials through tokens rather than storing passwords in plaintext
* It color-codes events based on the course they are for and whether they've been turned in (Maybe the other ones do this as well, I haven't checked)
* I wrote it (If we didn't become programmers to rewrite simple apps to solve our problems, what did we become programmers for?)

## Notes/Possible Improvements:
* I tried to get the code to ~~strikethrough~~ event names once assignments were completed and/or make transparent boxes like Canvas's calendar linking system, but I couldn't make that work
* I investigated using Google Tasks, but unfortunately, [they do not support times for due dates](https://issuetracker.google.com/issues/149537960)
* I was also interested in working on a webapp which puts a nice GUI interface over this script and handles all the Gradescope/Google Authentication, but at the moment, I don't have servers to run it on.
* I also want to add a feature to pull assignment descriptions and attachments and add them to the event description, but I haven't gotten around to it yet. Stay tuned!

## Setup
1. Clone the repository
2. Install the requirements with `pip install -r requirements.txt` (Google's APIs recommend using a virtual environment for this) ([Link to their instructions](https://github.com/googleapis/google-api-python-client/tree/main?tab=readme-ov-file#installation)  (It's not that hard))
3. Create a Google Cloud Platform project and enable the Google Calendar API ([Link to their instructions](https://developers.google.com/workspace/guides/create-project)) (The Calendar API is free) (This doesn't have to be on the same account you plan to use calendar for)
4. Create a Google Cloud Platform OAuth client ID ([Link to their instructions](https://developers.google.com/workspace/guides/create-credentials#desktop-app))
5. Create a file named `google_secrets.json` and add the following text:
``` Json
{
  "installed": {
    "client_id": "<YOUR CLIENT ID HERE>",
    "client_secret":"<YOUR CLIENT SECRET HERE>",
    "redirect_uris": ["http://localhost", "urn:ietf:wg:oauth:2.0:oob"],
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://accounts.google.com/o/oauth2/token"
  }
}
```
6. Extract the Gradescope token
    1. Log into Gradescope
    2. Open the developer tools (Usually F12)
    3. Go to the Application tab on Chrome/Chromium based browsers or the Storage tab on Firefox
    4. Expand the Cookies section
    5. Click on `https://www.gradescope.com`
    6. Click on the `signed_token` cookie
    7. In the bottom pane make sure "Show URL-Decoded" is checked (I couldn't find a good way to do this on Firefox)
    8. Copy the value of the `signed_token` cookie
7. Create a file named `gradescope_secrets.txt` and add the following text:
``` Json
{
    "gradescope_token": "<Your Token Here>"
}
```
8. Run `gradescope-calendar.py`
9. Follow the instructions in the terminal
    * This process will also have you assign colors to each course. The generated config file has a flag, `validate_colors`, which will check that the colors you've assigned are valid. I recommend leaving this on (the disadvantage is one extra API call and a few extra runtime checks). However, if you have a tested, working configuration and you really care about performance, you can turn it off. If you ever want to change your colors, I recommend turning it back on until you're sure you've got it right.
    * If you update your colors you might also want to delete `colors.json` and rerun the script to ensure your colors are up-to-date (although I doubt Google will change them anytime soon)
10. If you want to have the calendar continually update, you'll have to use something like Windows Task Scheduler to run the script periodically

Note the script also contains two command line switches `--log-to-file` and `--popup-on-error`. Because I am planning to run this through Windows Task Scheduler, they are just to make my life easier. They should be self-explanatory.

## Code Layout
The code is divide into two files:
* `gradescope-calendar.py` contains the main code/control flow login
* `utils.py` contains all the functions which do the heavy lifting
I think all the code is fairly organized/readable, but if you have any questions, feel free to open an issue!
