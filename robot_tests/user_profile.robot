*** Settings ***
Documentation     User profile: view, update, preferences (stub keywords, no real logic).
Suite Setup       Log Suite Start
Suite Teardown    Log Suite End
Test Setup        Log Test Start
Test Teardown     Log Test End

*** Keywords ***
Log Suite Start
    [Documentation]    Logs suite start.
    Log    Starting suite: User Profile

Log Suite End
    [Documentation]    Logs suite end.
    Log    Ending suite: User Profile

Log Test Start
    [Documentation]    Logs test start.
    Log    Starting test: ${TEST NAME}

Log Test End
    [Documentation]    Logs test end.
    Log    Ending test: ${TEST NAME}

Profile: Get Profile By User Id
    [Documentation]    Stub: would fetch profile from API/DB.
    [Arguments]    ${user_id}
    Log    Get profile for user_id=${user_id} (stub)  level=INFO
    Log    Error: This is an error message  level=ERROR
    Log    Warning: This is a warning message  level=WARN
    Log    Debug: This is a debug message  level=DEBUG
    Log    Trace: This is a trace message  level=TRACE
    &{profile}=    Create Dictionary    id=${user_id}    name=Stub User    email=stub@example.com
    RETURN    ${profile}

Profile: Update Profile Field
    [Documentation]    Stub: would update a single profile field.
    [Arguments]    ${user_id}    ${field}    ${value}
    Log    Update profile ${field}=${value} for user_id=${user_id} (stub)
    Log    Update successful (stub)

Profile: Get User Preferences
    [Documentation]    Stub: would return user preferences.
    [Arguments]    ${user_id}
    Log    Get preferences for user_id=${user_id} (stub)    level=INFO
    &{prefs}=    Create Dictionary    theme=dark    language=en    notifications=True
    RETURN    ${prefs}

Profile: Set User Preference
    [Documentation]    Stub: would set one preference.
    [Arguments]    ${user_id}    ${key}    ${value}
    Log    Set preference ${key}=${value} (stub)
    Log    Preference saved (stub)

Profile: Upload Avatar
    [Documentation]    Stub: would upload avatar image.
    [Arguments]    ${user_id}    ${file_path}
    Log    Upload avatar for user_id=${user_id} path=${file_path} (stub)
    ${url}=    Set Variable    https://example.com/avatars/${user_id}.png
    [Return]    ${url}

Test-Level Setup
    [Documentation]    Test-level setup keyword (runs before test body).
    Log    Test-level setup: preparing for test

Test-Level Teardown
    [Documentation]    Test-level teardown keyword (runs after test body).
    Log    Test-level teardown: cleaning up

Dictionary Should Contain Key
    [Documentation]    Keyword to check if a dictionary contains a key.
    [Arguments]    ${dictionary}    ${key}
    Should Contain    ${dictionary}    ${key}
    Log    Dictionary contains key: ${key}

*** Test Cases ***
Profile: Get Profile Returns Dict
    [Documentation]    Stub test: get profile by user id.
    [Tags]    profile    get    smoke

    ${profile}=    Profile: Get Profile By User Id    42
    Dictionary Should Contain Key    ${profile}    email
    Log    Profile: ${profile}



Profile: Update Profile Field Succeeds
    [Documentation]    Stub test: update single field.
    [Tags]    profile    update
    Profile: Update Profile Field    1    name    New Name
    Log    Field updated (stub)

Profile: Get User Preferences Returns Dict
    [Documentation]    Stub test: get preferences.
    [Tags]    profile    preferences
    ${prefs}=    Profile: Get User Preferences    10
    Dictionary Should Contain Key    ${prefs}    theme
    Log    Preferences: ${prefs}

Profile: Set User Preference Succeeds
    [Documentation]    Stub test: set preference.
    [Tags]    profile    preferences
    Profile: Set User Preference    5    theme    light
    Log    Preference set (stub)

Profile: Upload Avatar Returns Url
    [Documentation]    Stub test: upload avatar returns URL.
    [Tags]    profile    avatar
    ${url}=    Profile: Upload Avatar    7    /tmp/avatar.png
    Should Contain    ${url}    .png
    Log    Avatar URL: ${url}

Profile: Test With Test-Level Setup And Teardown
    [Documentation]    Uses test-level [Setup] and [Teardown] so they appear in the report (SETUP/TEARDOWN in Keyword Execution).
    [Setup]    Test-Level Setup
    [Teardown]    Test-Level Teardown
    [Tags]    profile    structure
    Log    Main test step
    No Operation

Profile: Skipped Not Implemented Yet
    [Documentation]    Placeholder test - not implemented yet.
    [Tags]    profile    wip    skip
    Skip    Not implemented yet.

Profile: Skipped Deprecated Flow
    [Documentation]    Skipped: deprecated profile flow.
    [Tags]    profile    deprecated
    Skip    Deprecated: use Profile: Get Profile Returns Dict instead.

Profile: Skipped Blocked By Bug
    [Documentation]    Skipped until backend bug is fixed.
    [Tags]    profile    blocked
    Skip    Blocked by ticket PROFILE-123.
