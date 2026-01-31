*** Settings ***
Documentation     Accounts: list, create, delete, balance (stub keywords, no real logic).
Suite Setup       Log Suite Start
Suite Teardown    Log Suite End
Test Setup        Log Test Start
Test Teardown     Log Test End

*** Keywords ***
Log Suite Start
    [Documentation]    Logs suite start.
    Log    Starting suite: Accounts

Log Suite End
    [Documentation]    Logs suite end.
    Log    Ending suite: Accounts

Log Test Start
    [Documentation]    Logs test start.
    Log    Starting test: ${TEST NAME}

Log Test End
    [Documentation]    Logs test end.
    Log    Ending test: ${TEST NAME}

Accounts: List Accounts For User
    [Documentation]    Stub: would return list of accounts for user.
    [Arguments]    ${user_id}
    Log    List accounts for user_id=${user_id} (stub)
    Log    Error: Sample error from Accounts suite (for report banner)    level=ERROR
    @{accounts}=    Create List    account_1    account_2
    RETURN    ${accounts}

Accounts: List Accounts For User
    [Documentation]    Stub: would return list of accounts for user.
    [Arguments]    ${user_id}
    Log    List accounts for user_id=${user_id} (stub)
    Log    Error: Sample error from Accounts suite (for report banner)    level=ERROR
    @{accounts}=    Create List    account_1    account_2
    RETURN    ${accounts}

Accounts: Create Account
    [Documentation]    Stub: would create new account.
    [Arguments]    ${user_id}    ${account_name}=Default
    Log    Create account ${account_name} for user_id=${user_id} (stub)
    ${account_id}=    Set Variable    acc_${user_id}_001
    RETURN    ${account_id}

Accounts: Delete Account
    [Documentation]    Stub: would delete account.
    [Arguments]    ${account_id}
    Log    Delete account ${account_id} (stub)
    Log    Account deleted (stub)

Accounts: Get Account Balance
    [Documentation]    Stub: would return balance.
    [Arguments]    ${account_id}
    Log    Get balance for ${account_id} (stub)
    ${balance}=    Set Variable    1000.00
    RETURN    ${balance}

Accounts: Account Exists
    [Documentation]    Stub: would check if account exists.
    [Arguments]    ${account_id}
    Log    Check exists ${account_id} (stub)
    ${exists}=    Set Variable    True
    RETURN    ${exists}    ${exists}


*** Test Cases ***
Accounts: List Accounts Returns Non Empty
    [Documentation]    Stub test: list accounts for user.
    [Tags]    accounts    list    smoke
    @{accounts}=    Accounts: List Accounts For User    1
    Length Should Be    ${accounts}    2
    Log    Accounts: ${accounts}

Accounts: Create Account Returns Id
    [Documentation]    Stub test: create account.
    [Tags]    accounts    create
    ${account_id}=    Accounts: Create Account    5    My Account
    Should Not Be Empty    ${account_id}
    Log    Created: ${account_id}

Accounts: Delete Account Succeeds
    [Documentation]    Stub test: delete account.
    [Tags]    accounts    delete
    Accounts: Delete Account    acc_99_001
    Log    Delete completed (stub)

Accounts: Get Balance Returns Number
    [Documentation]    Stub test: get balance.
    [Tags]    accounts    balance
    ${balance}=    Accounts: Get Account Balance    acc_1_001
    Should Be Equal As Numbers    ${balance}    1000.00
    Log    Balance: ${balance}

Accounts: Account Exists Returns True
    [Documentation]    Stub test: account exists check.
    [Tags]    accounts    exists
    ${exists}=    Accounts: Account Exists    acc_1_001
    Should Be True    ${exists}
    Log    Exists: ${exists}
