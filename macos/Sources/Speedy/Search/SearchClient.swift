import Foundation

/// Errors the overlay can render to the user. Anything that doesn't fit
/// these buckets bubbles up as `.transport(message:)` so we don't ever
/// silently lose a failure path.
enum SearchError: Error, Equatable {
    case transport(message: String)
    case http(status: Int)
    case decode(message: String)
}

/// Protocol so the overlay can be tested with a fake without touching the
/// network. Production wiring uses `HTTPSearchClient`.
protocol SearchClient: Sendable {
    func search(_ selection: Selection) async throws -> SearchOutcome
}

/// Default `URLSession`-backed client.
///
/// Backend URL precedence:
/// 1. `SPEEDY_BACKEND_URL` environment variable (set in Xcode scheme for dev)
/// 2. `SpeedyBackendURL` Info.plist string (for shipped builds)
/// 3. `http://localhost:8000` fallback (so a fresh checkout works against a
///    local uvicorn without any config)
final class HTTPSearchClient: SearchClient {
    private let baseURL: URL
    private let session: URLSession
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(baseURL: URL? = nil, session: URLSession = .shared) {
        self.baseURL = baseURL ?? Self.resolveBaseURL()
        self.session = session

        encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase

        decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
    }

    func search(_ selection: Selection) async throws -> SearchOutcome {
        var request = URLRequest(url: baseURL.appendingPathComponent("search"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 5
        let body = SearchRequestBody(
            highlight: selection.highlight,
            surroundingContext: selection.surroundingContext,
            pageTitle: selection.pageTitle
        )
        request.httpBody = try encoder.encode(body)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw SearchError.transport(message: error.localizedDescription)
        }

        guard let http = response as? HTTPURLResponse else {
            throw SearchError.transport(message: "non-HTTP response")
        }
        guard (200..<300).contains(http.statusCode) else {
            throw SearchError.http(status: http.statusCode)
        }

        do {
            let decoded = try decoder.decode(SearchResponse.self, from: data)
            return SearchOutcome(decoded)
        } catch {
            throw SearchError.decode(message: error.localizedDescription)
        }
    }

    static func resolveBaseURL() -> URL {
        if let env = ProcessInfo.processInfo.environment["SPEEDY_BACKEND_URL"],
           let url = URL(string: env) {
            return url
        }
        if let plist = Bundle.main.object(forInfoDictionaryKey: "SpeedyBackendURL") as? String,
           let url = URL(string: plist) {
            return url
        }
        return URL(string: "http://localhost:8000")!
    }
}

private struct SearchRequestBody: Encodable {
    let highlight: String
    let surroundingContext: String?
    let pageTitle: String?
}
