import Foundation

// MARK: - GET /users/{id}/batteries

struct BatteriesResponse: Codable {
    let garminUserId: String
    let devices: [DeviceBattery]

    enum CodingKeys: String, CodingKey {
        case garminUserId = "garmin_user_id"
        case devices
    }
}

struct DeviceBattery: Codable, Identifiable {
    var id: String { serialNumber.map(String.init) ?? deviceName }

    let deviceName: String
    let classification: String?
    let manufacturer: String?
    let serialNumber: Int?
    let batteryVoltage: Double?
    let batteryStatus: String?
    let batteryLevel: Int?
    let softwareVersion: String?
    let fromActivity: String?
    let activityTime: String?

    enum CodingKeys: String, CodingKey {
        case deviceName = "device_name"
        case classification
        case manufacturer
        case serialNumber = "serial_number"
        case batteryVoltage = "battery_voltage"
        case batteryStatus = "battery_status"
        case batteryLevel = "battery_level"
        case softwareVersion = "software_version"
        case fromActivity = "from_activity"
        case activityTime = "activity_time"
    }

    var isOk: Bool {
        guard let status = batteryStatus else { return true }
        return ["ok", "good", "new"].contains(status)
    }

    var statusColor: String {
        guard let status = batteryStatus else { return "gray" }
        switch status {
        case "ok", "good", "new": return "green"
        case "low": return "yellow"
        case "critical": return "red"
        default: return "gray"
        }
    }
}

// MARK: - GET /users/{id}/battery-history

struct AllDeviceHistoryResponse: Codable {
    let garminUserId: String
    let devices: [String: [BatteryReading]]

    enum CodingKeys: String, CodingKey {
        case garminUserId = "garmin_user_id"
        case devices
    }
}

struct BatteryReading: Codable, Identifiable {
    var id: String { "\(garminActivityId ?? "")_\(activityTime ?? "")" }

    let activityTime: String?
    let batteryVoltage: Double?
    let batteryStatus: String?
    let batteryLevel: Int?
    let activityType: String?
    let garminActivityId: String?

    enum CodingKeys: String, CodingKey {
        case activityTime = "activity_time"
        case batteryVoltage = "battery_voltage"
        case batteryStatus = "battery_status"
        case batteryLevel = "battery_level"
        case activityType = "activity_type"
        case garminActivityId = "garmin_activity_id"
    }

    var date: Date? {
        guard let activityTime else { return nil }
        return ISO8601DateFormatter().date(from: activityTime)
    }
}

// MARK: - GET /users/{id}/activities

struct ActivitiesResponse: Codable {
    let garminUserId: String
    let activities: [Activity]

    enum CodingKeys: String, CodingKey {
        case garminUserId = "garmin_user_id"
        case activities
    }
}

struct Activity: Codable, Identifiable {
    var id: String { garminActivityId }

    let garminActivityId: String
    let activityType: String?
    let deviceName: String?
    let startTime: String?
    let processingStatus: String?

    enum CodingKeys: String, CodingKey {
        case garminActivityId = "garmin_activity_id"
        case activityType = "activity_type"
        case deviceName = "device_name"
        case startTime = "start_time"
        case processingStatus = "processing_status"
    }
}
