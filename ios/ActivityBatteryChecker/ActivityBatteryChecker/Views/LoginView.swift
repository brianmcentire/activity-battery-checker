import SwiftUI

struct LoginView: View {
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        VStack(spacing: 32) {
            Spacer()

            VStack(spacing: 12) {
                Image(systemName: "battery.100.bolt")
                    .font(.system(size: 64))
                    .foregroundStyle(.blue)

                Text("Activity Battery Checker")
                    .font(.title.bold())

                Text("Monitor your fitness sensor batteries")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Button {
                authManager.login()
            } label: {
                HStack {
                    if authManager.isAuthenticating {
                        ProgressView()
                            .tint(.white)
                    }
                    Text("Connect to Garmin")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(.blue)
                .foregroundStyle(.white)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .disabled(authManager.isAuthenticating)
            .padding(.horizontal, 32)

            Spacer()
                .frame(height: 60)
        }
    }
}
