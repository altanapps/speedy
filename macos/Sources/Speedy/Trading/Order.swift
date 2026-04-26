import Foundation

/// Mirrors `app.api.OrderRequest` (Pydantic) on the backend. Snake-cased
/// over the wire via `JSONEncoder.keyEncodingStrategy = .convertToSnakeCase`.
struct OrderRequest: Codable, Equatable, Sendable {
    let marketId: String
    let outcome: Outcome
    let sizeUsdc: Double
    let side: Side

    enum Outcome: String, Codable, Equatable, Sendable {
        case yes = "Yes"
        case no = "No"
    }

    enum Side: String, Codable, Equatable, Sendable {
        case buy = "BUY"
        case sell = "SELL"
    }
}

/// Mirrors `app.api.OrderResponse`. `error` is non-nil when the CLOB rejected
/// us (insufficient balance, no liquidity, etc.) — those still come back as
/// HTTP 200 with a structured error rather than an HTTP 5xx, so the overlay
/// can render a one-line failure row instead of a generic transport error.
struct OrderResponse: Codable, Equatable, Sendable {
    let orderId: String?
    let status: String
    let transactionHash: String?
    let error: String?

    enum CodingKeys: String, CodingKey {
        case orderId = "order_id"
        case status
        case transactionHash = "transaction_hash"
        case error
    }
}
