import AuthenticationServices
import Foundation

@MainActor
class AuthManager: ObservableObject {
    @Published var userId: String?
    @Published var isAuthenticating = false

    private let userIdKey = "garminUserId"

    init() {
        userId = UserDefaults.standard.string(forKey: userIdKey)
    }

    var isLoggedIn: Bool { userId != nil }

    func login() {
        let connectURL = APIClient.shared.baseURL
            .appendingPathComponent("auth/connect")
            .appending(queryItems: [URLQueryItem(name: "redirect", value: "app")])

        let callbackScheme = "activitybattery"

        let session = ASWebAuthenticationSession(
            url: connectURL,
            callbackURLScheme: callbackScheme
        ) { [weak self] callbackURL, error in
            Task { @MainActor in
                self?.isAuthenticating = false
                guard let url = callbackURL, error == nil else { return }
                self?.handleCallback(url: url)
            }
        }

        session.prefersEphemeralWebBrowserSession = false
        session.presentationContextProvider = ASWebAuthPresentationContext.shared
        isAuthenticating = true
        session.start()
    }

    func handleCallback(url: URL) {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let userParam = components.queryItems?.first(where: { $0.name == "user" })?.value
        else { return }

        userId = userParam
        UserDefaults.standard.set(userParam, forKey: userIdKey)
    }

    func logout() {
        userId = nil
        UserDefaults.standard.removeObject(forKey: userIdKey)
    }
}

// Presentation context for ASWebAuthenticationSession
class ASWebAuthPresentationContext: NSObject, ASWebAuthenticationPresentationContextProviding {
    static let shared = ASWebAuthPresentationContext()

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        ASPresentationAnchor()
    }
}
