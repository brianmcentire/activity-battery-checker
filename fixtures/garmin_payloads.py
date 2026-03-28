"""
Simulated Garmin webhook payloads for local testing.
"""

ACTIVITY_SUMMARY_OUTDOOR_RIDE = {
    "activitySummaries": [
        {
            "userId": "test-user-001",
            "userAccessToken": "fake-access-token",
            "summaryId": "summary-12345",
            "activityId": 99001,
            "activityName": "Afternoon Ride",
            "activityType": "ROAD_BIKING",
            "deviceName": "Edge 1040",
            "manual": False,
            "startTimeInSeconds": 1711600000,
            "durationInSeconds": 3600,
        }
    ]
}

ACTIVITY_SUMMARY_INDOOR_RIDE = {
    "activitySummaries": [
        {
            "userId": "test-user-001",
            "userAccessToken": "fake-access-token",
            "summaryId": "summary-12346",
            "activityId": 99002,
            "activityName": "Indoor Trainer",
            "activityType": "INDOOR_CYCLING",
            "deviceName": "Edge 1040",
            "manual": False,
            "startTimeInSeconds": 1711610000,
            "durationInSeconds": 2700,
        }
    ]
}

ACTIVITY_SUMMARY_VIRTUAL_RIDE = {
    "activitySummaries": [
        {
            "userId": "test-user-001",
            "userAccessToken": "fake-access-token",
            "summaryId": "summary-12347",
            "activityId": 99003,
            "activityName": "Zwift Race",
            "activityType": "VIRTUAL_RIDE",
            "deviceName": "Edge 1040",
            "manual": False,
            "startTimeInSeconds": 1711620000,
            "durationInSeconds": 1800,
        }
    ]
}

ACTIVITY_SUMMARY_MANUAL = {
    "activitySummaries": [
        {
            "userId": "test-user-001",
            "userAccessToken": "fake-access-token",
            "summaryId": "summary-12348",
            "activityId": 99004,
            "activityName": "Manual Entry",
            "activityType": "CYCLING",
            "deviceName": None,
            "manual": True,
            "startTimeInSeconds": 1711630000,
            "durationInSeconds": 5400,
        }
    ]
}

ACTIVITY_FILE_FIT = {
    "activityFiles": [
        {
            "userId": "test-user-001",
            "userAccessToken": "fake-access-token",
            "summaryId": "summary-12345",
            "activityId": 99001,
            "fileType": "FIT",
            "callbackURL": "https://apis.garmin.com/activity-service/activity/fake-callback-url",
        }
    ]
}

ACTIVITY_FILE_TCX = {
    "activityFiles": [
        {
            "userId": "test-user-001",
            "userAccessToken": "fake-access-token",
            "summaryId": "summary-12345",
            "activityId": 99001,
            "fileType": "TCX",
            "callbackURL": "https://apis.garmin.com/activity-service/activity/fake-callback-url-tcx",
        }
    ]
}

DEREGISTRATION = {
    "deregistrations": [
        {
            "userId": "test-user-001",
            "userAccessToken": "fake-access-token",
        }
    ]
}

PERMISSION_CHANGE = {
    "permissionChanges": [
        {
            "userId": "test-user-001",
            "userAccessToken": "fake-access-token",
            "permissions": ["ACTIVITY_SUMMARY", "ACTIVITY_FILE"],
        }
    ]
}

MULTI_ACTIVITY_SUMMARY = {
    "activitySummaries": [
        {
            "userId": "test-user-001",
            "userAccessToken": "fake-access-token",
            "summaryId": "summary-20001",
            "activityId": 20001,
            "activityType": "ROAD_BIKING",
            "deviceName": "Edge 1040",
            "manual": False,
            "startTimeInSeconds": 1711700000,
        },
        {
            "userId": "test-user-001",
            "userAccessToken": "fake-access-token",
            "summaryId": "summary-20002",
            "activityId": 20002,
            "activityType": "INDOOR_CYCLING",
            "deviceName": "Edge 1040",
            "manual": False,
            "startTimeInSeconds": 1711690000,
        },
        {
            "userId": "test-user-001",
            "userAccessToken": "fake-access-token",
            "summaryId": "summary-20003",
            "activityId": 20003,
            "activityType": "VIRTUAL_RIDE",
            "deviceName": "Edge 1040",
            "manual": False,
            "startTimeInSeconds": 1711680000,
        },
    ]
}
