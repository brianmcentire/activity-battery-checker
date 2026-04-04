import Foundation

class APIClient {
    static let shared = APIClient()

    // During development: localhost for simulator, ngrok for real device
    var baseURL: URL {
        URL(string: UserDefaults.standard.string(forKey: "serverURL") ?? "http://localhost:8000")!
    }

    private let session = URLSession.shared
    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        return d
    }()

    // MARK: - Batteries

    func getDeviceBatteries(userId: String) async throws -> BatteriesResponse {
        let url = baseURL.appendingPathComponent("users/\(userId)/batteries")
        return try await fetch(url)
    }

    // MARK: - Battery History

    func getBatteryHistory(userId: String) async throws -> AllDeviceHistoryResponse {
        let url = baseURL.appendingPathComponent("users/\(userId)/battery-history")
        return try await fetch(url)
    }

    // MARK: - Activities

    func getActivities(userId: String, limit: Int = 20) async throws -> ActivitiesResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("users/\(userId)/activities"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "limit", value: String(limit))]
        return try await fetch(components.url!)
    }

    // MARK: - Private

    private func fetch<T: Decodable>(_ url: URL) async throws -> T {
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            let code = (response as? HTTPURLResponse)?.statusCode ?? -1
            throw APIError.httpError(statusCode: code)
        }
        return try decoder.decode(T.self, from: data)
    }
}

enum APIError: LocalizedError {
    case httpError(statusCode: Int)

    var errorDescription: String? {
        switch self {
        case .httpError(let code):
            return "Server returned status \(code)"
        }
    }
}
