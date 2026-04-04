import Charts
import SwiftUI

struct BatteryChartView: View {
    let history: [String: [BatteryReading]]
    let devices: [DeviceBattery]

    /// Map device serial/key to a friendly name using the devices list
    private func deviceName(for key: String) -> String {
        if let device = devices.first(where: {
            ($0.serialNumber.map(String.init) ?? $0.deviceName) == key
        }) {
            return device.deviceName
        }
        return key
    }

    private var chartData: [(device: String, date: Date, voltage: Double)] {
        history.flatMap { key, readings in
            readings.compactMap { reading in
                guard let date = reading.date, let voltage = reading.batteryVoltage else {
                    return nil as (String, Date, Double)?
                }
                return (deviceName(for: key), date, voltage)
            }
        }
        .sorted { $0.date < $1.date }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Voltage History")
                .font(.headline)

            if chartData.isEmpty {
                Text("No voltage data available")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 150)
            } else {
                Chart(chartData, id: \.device) { point in
                    LineMark(
                        x: .value("Date", point.date),
                        y: .value("Voltage", point.voltage)
                    )
                    .foregroundStyle(by: .value("Device", point.device))

                    PointMark(
                        x: .value("Date", point.date),
                        y: .value("Voltage", point.voltage)
                    )
                    .foregroundStyle(by: .value("Device", point.device))
                    .symbolSize(20)
                }
                .chartYAxisLabel("Volts")
                .chartLegend(position: .bottom)
                .frame(height: 250)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
