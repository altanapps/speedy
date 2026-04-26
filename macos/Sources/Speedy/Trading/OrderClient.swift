import Foundation

/// Errors the overlay can render. Mirrors `SearchError`'s shape so the
/// describe()-style adapter in OverlayController stays uniform.
enum OrderError: Error, Equatable {
    case transport(message: String)
    /// HTTP 4xx/5xx with the backend's `detail` string when available.
    case http(status: Int, message: String?)
    case decode(message: String)
    /// HTTP 200 with `error` set in the body — i.e. the CLOB rejected the
    /// order at the application layer (insufficient USDC, no liquidity, etc.).
    case rejected(message: String)
    /// Backend signaled the operator hasn't configured POLYMARKET_PRIVATE_KEY.
    /// Keep this distinct so we can tell the user *what* to fix.
    case credentialsMissing(message: String)
}

protocol OrderClient: Sendable {
    func placeOrder(_ request: OrderRequest) async throws -> OrderResponse
}

/// `URLSession`-backed client. Backend URL precedence matches `HTTPSearchClient`:
/// 1. `SPEEDY_BACKEND_URL` env var
/// 2. Info.plist `SpeedyBackendURL`
/// 3. `http://localhost:8000`
final class HTTPOrderClient: OrderClient {
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
    }

    func placeOrder(_ request: OrderRequest) async throws -> OrderResponse {
        var urlRequest = URLRequest(url: baseURL.appendingPathComponent("order"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        // Order placement can be slow — CLOB has to sign and broadcast on
        // Polygon. 15s gives matched-trade settlement time without leaving
        // the user staring at a spinner forever.
        urlRequest.timeoutInterval = 15
        urlRequest.httpBody = try encoder.encode(request)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: urlRequest)
        } catch {
            throw OrderError.transport(message: error.localizedDescription)
        }

        guard let http = response as? HTTPURLResponse else {
            throw OrderError.transport(message: "non-HTTP response")
        }

        if !(200..<300).contains(http.statusCode) {
            // Pull FastAPI's `detail` field out of the error body if we can —
            // gives the overlay something more actionable than "HTTP 503".
            let detail = Self.extractDetail(from: data)
            if http.statusCode == 503 {
                throw OrderError.credentialsMissing(
                    message: detail ?? "Backend missing POLYMARKET_PRIVATE_KEY."
                )
            }
            throw OrderError.http(status: http.statusCode, message: detail)
        }

        let decoded: OrderResponse
        do {
            decoded = try decoder.decode(OrderResponse.self, from: data)
        } catch {
            throw OrderError.decode(message: error.localizedDescription)
        }
        if let err = decoded.error, !err.isEmpty {
            throw OrderError.rejected(message: err)
        }
        return decoded
    }

    private static func extractDetail(from data: Data) -> String? {
        guard
            let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return nil }
        return obj["detail"] as? String
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
