import SwiftUI

struct DeviceListView: View {
    let devices: [DeviceBattery]

    /// Sorted: alerts first, then alphabetical by device name
    private var sortedDevices: [DeviceBattery] {
        devices.sorted { a, b in
            if a.isOk != b.isOk { return !a.isOk }
            return a.deviceName.localizedCompare(b.deviceName) == .orderedAscending
        }
    }

    var body: some View {
        if devices.isEmpty {
            VStack(spacing: 12) {
                Image(systemName: "antenna.radiowaves.left.and.right.slash")
                    .font(.largeTitle)
                    .foregroundStyle(.secondary)
                Text("No devices yet")
                    .font(.headline)
                Text("Complete an activity with paired sensors to see battery data.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            .frame(maxWidth: .infinity, minHeight: 150)
            .padding()
        } else {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 160), spacing: 12)], spacing: 12) {
                ForEach(sortedDevices) { device in
                    DeviceCardView(device: device)
                }
            }
        }
    }
}
