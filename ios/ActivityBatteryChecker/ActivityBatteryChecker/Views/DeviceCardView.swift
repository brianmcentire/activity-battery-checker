import SwiftUI

struct DeviceCardView: View {
    let device: DeviceBattery

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(device.deviceName)
                    .font(.subheadline.bold())
                    .lineLimit(1)
                Spacer()
                statusBadge
            }

            if let voltage = device.batteryVoltage {
                HStack(spacing: 4) {
                    Image(systemName: "bolt.fill")
                        .font(.caption2)
                        .foregroundStyle(.yellow)
                    Text(String(format: "%.3f V", voltage))
                        .font(.caption.monospacedDigit())
                }
            }

            if let level = device.batteryLevel {
                HStack(spacing: 4) {
                    Image(systemName: batteryIcon(level: level))
                        .font(.caption2)
                        .foregroundStyle(batteryColor)
                    Text("\(level)%")
                        .font(.caption.monospacedDigit())
                }
            }

            if let time = device.activityTime {
                Text(formatDate(time))
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .background(device.isOk ? Color(.systemGray6) : Color.red.opacity(0.15))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(device.isOk ? Color(.systemGray4) : Color.red.opacity(0.4), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private var statusBadge: some View {
        Text(device.batteryStatus?.capitalized ?? "Unknown")
            .font(.caption2.bold())
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(badgeColor.opacity(0.2))
            .foregroundStyle(badgeColor)
            .clipShape(Capsule())
    }

    private var badgeColor: Color {
        switch device.statusColor {
        case "green": return .green
        case "yellow": return .yellow
        case "red": return .red
        default: return .gray
        }
    }

    private var batteryColor: Color {
        guard let level = device.batteryLevel else { return .gray }
        if level > 50 { return .green }
        if level > 20 { return .yellow }
        return .red
    }

    private func batteryIcon(level: Int) -> String {
        if level > 75 { return "battery.100" }
        if level > 50 { return "battery.75" }
        if level > 25 { return "battery.50" }
        return "battery.25"
    }

    private func formatDate(_ iso: String) -> String {
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: iso) else { return iso }
        let display = DateFormatter()
        display.dateStyle = .medium
        display.timeStyle = .short
        return display.string(from: date)
    }
}
