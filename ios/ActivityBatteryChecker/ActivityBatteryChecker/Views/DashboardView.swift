import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var devices: [DeviceBattery] = []
    @State private var history: [String: [BatteryReading]] = [:]
    @State private var isLoading = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    if isLoading && devices.isEmpty {
                        ProgressView("Loading...")
                            .frame(maxWidth: .infinity, minHeight: 200)
                    } else if let error {
                        VStack(spacing: 12) {
                            Image(systemName: "exclamationmark.triangle")
                                .font(.largeTitle)
                                .foregroundStyle(.yellow)
                            Text(error)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.center)
                            Button("Retry") { Task { await refresh() } }
                                .buttonStyle(.bordered)
                        }
                        .frame(maxWidth: .infinity, minHeight: 200)
                    } else {
                        DeviceListView(devices: devices)

                        if !history.isEmpty {
                            BatteryChartView(history: history, devices: devices)
                        }
                    }
                }
                .padding()
            }
            .refreshable { await refresh() }
            .navigationTitle("Batteries")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button("Disconnect", role: .destructive) {
                            authManager.logout()
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
        }
        .task { await refresh() }
    }

    private func refresh() async {
        guard let userId = authManager.userId else { return }
        isLoading = true
        error = nil

        do {
            async let batteriesReq = APIClient.shared.getDeviceBatteries(userId: userId)
            async let historyReq = APIClient.shared.getBatteryHistory(userId: userId)

            let (batteriesResp, historyResp) = try await (batteriesReq, historyReq)
            devices = batteriesResp.devices
            history = historyResp.devices
        } catch {
            self.error = error.localizedDescription
        }

        isLoading = false
    }
}
