import Foundation

/// Mirror of the backend's `MatchedMarket` Pydantic model. Field-for-field;
/// snake_case → camelCase via `CodingKeys`.
struct MatchedMarket: Codable, Equatable, Sendable {
    let id: String
    let slug: String
    let question: String
    let description: String?
    let endDate: Date?
    let category: String?
    let tags: [String]?

    enum CodingKeys: String, CodingKey {
        case id
        case slug
        case question
        case description
        case endDate = "end_date"
        case category
        case tags
    }
}

/// Mirror of `SearchResponse`. `match` is nil when the top-1 score didn't
/// clear the configured threshold; the score and threshold are still
/// returned so debug UI can show "we looked, here's why we said no."
struct SearchResponse: Codable, Equatable, Sendable {
    let match: MatchedMarket?
    let score: Double?
    let threshold: Double
}

/// What the overlay actually consumes. Collapses the wire shape into
/// "did we have a match or not" + the metadata for either branch.
enum SearchOutcome: Equatable, Sendable {
    case matched(MatchedMarket, score: Double, threshold: Double)
    case noMatch(score: Double?, threshold: Double)

    init(_ response: SearchResponse) {
        if let market = response.match, let score = response.score {
            self = .matched(market, score: score, threshold: response.threshold)
        } else {
            self = .noMatch(score: response.score, threshold: response.threshold)
        }
    }
}
