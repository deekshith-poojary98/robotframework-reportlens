*** Settings ***
Documentation     Payments: charge, refund, history (stub keywords, no real logic).
Suite Setup       Log Suite Start
Suite Teardown    Log Suite End
Test Setup        Log Test Start
Test Teardown     Log Test End

*** Keywords ***
Log Suite Start
    [Documentation]    Logs suite start.
    Log    Starting suite: Payments

Log Suite End
    [Documentation]    Logs suite end.
    Log    Ending suite: Payments

Log Test Start
    [Documentation]    Logs test start.
    Log    Starting test: ${TEST NAME}

Log Test End
    [Documentation]    Logs test end.
    Log    Ending test: ${TEST NAME}

Payments: Charge Card
    [Documentation]    Stub: would charge payment method.
    [Arguments]    ${account_id}    ${amount}    ${currency}=USD
    Log    Charge ${amount} ${currency} for account ${account_id} (stub)
    ${charge_id}=    Set Variable    ch_001
    RETURN    ${charge_id}

Payments: Refund Payment
    [Documentation]    Stub: would refund a charge.
    [Arguments]    ${charge_id}    ${amount}=
    Log    Refund charge ${charge_id} (stub)
    ${refund_id}=    Set Variable    rf_001
    RETURN    ${refund_id}

Payments: Get Payment History
    [Documentation]    Stub: would return list of payments.
    [Arguments]    ${account_id}    ${limit}=10
    Log    Get payment history for ${account_id} limit=${limit} (stub)
    @{history}=    Create List    payment_1    payment_2
    RETURN    ${history}

Payments: Get Charge Status
    [Documentation]    Stub: would return charge status.
    [Arguments]    ${charge_id}
    Log    Get status for charge ${charge_id} (stub)
    ${status}=    Set Variable    succeeded
    [Return]    ${status}

Payments: Add Payment Method
    [Documentation]    Stub: would add card/payment method.
    [Arguments]    ${account_id}    ${payment_token}
    Log    Add payment method for account ${account_id} (stub)
    ${method_id}=    Set Variable    pm_001
    RETURN    ${method_id}


*** Test Cases ***
Payments: Charge Card Returns Charge Id
    [Documentation]    Stub test: charge card.
    [Tags]    payments    charge    smoke
    ${charge_id}=    Payments: Charge Card    1    99.99    USD
    Should Not Be Empty    ${charge_id}
    Log    Charge id: ${charge_id}

Payments: Refund Payment Returns Refund Id
    [Documentation]    Stub test: refund.
    [Tags]    payments    refund
    ${refund_id}=    Payments: Refund Payment    ch_001    50.00
    Should Not Be Empty    ${refund_id}
    Log    Refund id: ${refund_id}

Payments: Get Payment History Returns List
    [Documentation]    Stub test: payment history.
    [Tags]    payments    history
    @{history}=    Payments: Get Payment History    1    5
    Length Should Be    ${history}    2
    Log    History: ${history}

Payments: Get Charge Status Returns Succeeded
    [Documentation]    Stub test: charge status.
    [Tags]    payments    status
    ${status}=    Payments: Get Charge Status    ch_001
    Should Be Equal    ${status}    succeeded
    Log    Status: ${status}

Payments: Add Payment Method Returns Method Id
    [Documentation]    Stub test: add payment method.
    [Tags]    payments    method
    ${method_id}=    Payments: Add Payment Method    1    tok_abc123
    Should Not Be Empty    ${method_id}
    Log    Method id: ${method_id}
