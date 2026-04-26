import Foundation

/// Mirrors the backend's ConfigResponse. Fields can be nil if the backend
/// isn't configured for trading yet (no POLYMARKET_FUNDER_ADDRESS set).
struct BackendConfig: Codable, Equatable, Sendable {
    let funderAddress: String?
    let polymarketProfileUrl: String?

    enum CodingKeys: String, CodingKey {
        case funderAddress = "funder_address"
        case polymarketProfileUrl = "polymarket_profile_url"
    }
}

/// One-shot GET /config. Used at app launch to discover the user's
/// Polymarket profile URL so the overlay can deep-link to their positions.
/// Failure is non-fatal — overlay falls back to /portfolio.
final class ConfigClient: Sendable {
    private let baseURL: URL
    private let session: URLSession

    init(baseURL: URL? = nil, session: URLSession = .shared) {
        self.baseURL = baseURL ?? HTTPSearchClient.resolveBaseURL()
        self.session = session
    }

    func fetch() async -> BackendConfig? {
        var request = URLRequest(url: baseURL.appendingPathComponent("config"))
        request.timeoutInterval = 3
        do {
            let (data, response) = try await session.data(for: request)
            guard
                let http = response as? HTTPURLResponse,
                (200..<300).contains(http.statusCode)
            else { return nil }
            return try JSONDecoder().decode(BackendConfig.self, from: data)
        } catch {
            return nil
        }
    }
}
