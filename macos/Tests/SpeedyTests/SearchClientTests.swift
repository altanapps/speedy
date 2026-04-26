import Foundation
import XCTest

@testable import Speedy

/// Stubs all `URLSession` traffic at the URLProtocol layer so the test runs
/// without real networking. Each test sets `Stub.handler` to whatever it
/// wants the response to be.
final class SearchClientTests: XCTestCase {
    private var session: URLSession!

    override func setUp() {
        super.setUp()
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        session = URLSession(configuration: config)
    }

    override func tearDown() {
        StubURLProtocol.handler = nil
        super.tearDown()
    }

    private func client() -> HTTPSearchClient {
        HTTPSearchClient(baseURL: URL(string: "http://test.local")!, session: session)
    }

    private let selection = Selection(
        highlight: "Powell",
        surroundingContext: nil,
        pageTitle: "Reuters",
        source: .accessibility
    )

    func test_match_decodesIntoMatchedOutcome() async throws {
        StubURLProtocol.handler = { _ in
            let json = #"""
            {
              "match": {
                "id": "fed-may-cut",
                "slug": "fed-may-cut",
                "question": "Fed cut at May FOMC?",
                "description": null,
                "end_date": "2026-05-07T20:00:00+00:00",
                "category": "Macro",
                "tags": ["fed", "rates"]
              },
              "score": 0.71,
              "threshold": 0.55
            }
            """#
            return (
                HTTPURLResponse(url: URL(string: "http://test.local/search")!,
                                statusCode: 200, httpVersion: nil, headerFields: nil)!,
                Data(json.utf8)
            )
        }

        let outcome = try await client().search(selection)
        guard case let .matched(market, score, threshold) = outcome else {
            return XCTFail("expected matched, got \(outcome)")
        }
        XCTAssertEqual(market.id, "fed-may-cut")
        XCTAssertEqual(market.tags, ["fed", "rates"])
        XCTAssertEqual(score, 0.71, accuracy: 0.001)
        XCTAssertEqual(threshold, 0.55, accuracy: 0.001)
    }

    func test_noMatch_returnsNoMatchOutcome() async throws {
        StubURLProtocol.handler = { _ in
            let json = #"{"match": null, "score": null, "threshold": 0.55}"#
            return (
                HTTPURLResponse(url: URL(string: "http://test.local/search")!,
                                statusCode: 200, httpVersion: nil, headerFields: nil)!,
                Data(json.utf8)
            )
        }

        let outcome = try await client().search(selection)
        guard case let .noMatch(score, threshold) = outcome else {
            return XCTFail("expected noMatch, got \(outcome)")
        }
        XCTAssertNil(score)
        XCTAssertEqual(threshold, 0.55, accuracy: 0.001)
    }

    func test_http500_throwsHttpError() async {
        StubURLProtocol.handler = { _ in
            (
                HTTPURLResponse(url: URL(string: "http://test.local/search")!,
                                statusCode: 500, httpVersion: nil, headerFields: nil)!,
                Data()
            )
        }

        do {
            _ = try await client().search(selection)
            XCTFail("expected throw")
        } catch let SearchError.http(status) {
            XCTAssertEqual(status, 500)
        } catch {
            XCTFail("wrong error: \(error)")
        }
    }

    func test_decodeFailure_throwsDecodeError() async {
        StubURLProtocol.handler = { _ in
            (
                HTTPURLResponse(url: URL(string: "http://test.local/search")!,
                                statusCode: 200, httpVersion: nil, headerFields: nil)!,
                Data("not-json".utf8)
            )
        }

        do {
            _ = try await client().search(selection)
            XCTFail("expected throw")
        } catch SearchError.decode {
            // ok
        } catch {
            XCTFail("wrong error: \(error)")
        }
    }

    func test_request_serializesSnakeCaseAndPostsToSearch() async throws {
        var captured: URLRequest?
        StubURLProtocol.handler = { request in
            captured = request
            let json = #"{"match": null, "score": null, "threshold": 0.55}"#
            return (
                HTTPURLResponse(url: request.url!,
                                statusCode: 200, httpVersion: nil, headerFields: nil)!,
                Data(json.utf8)
            )
        }

        let sel = Selection(
            highlight: "rates",
            surroundingContext: "Fed signals patience",
            pageTitle: "FT",
            source: .accessibility
        )
        _ = try await client().search(sel)

        let request = try XCTUnwrap(captured)
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/search")

        let body = try XCTUnwrap(StubURLProtocol.lastBody)
        let parsed = try JSONSerialization.jsonObject(with: body) as? [String: Any]
        XCTAssertEqual(parsed?["highlight"] as? String, "rates")
        XCTAssertEqual(parsed?["surrounding_context"] as? String, "Fed signals patience")
        XCTAssertEqual(parsed?["page_title"] as? String, "FT")
    }
}

// MARK: - URLProtocol stub

final class StubURLProtocol: URLProtocol {
    nonisolated(unsafe) static var handler: ((URLRequest) -> (HTTPURLResponse, Data))?
    nonisolated(unsafe) static var lastBody: Data?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        // URLSession reads the body via httpBodyStream when used with
        // ephemeral configs + URLProtocol; capture it here so tests can
        // assert on what was sent.
        if let stream = request.httpBodyStream {
            Self.lastBody = StubURLProtocol.read(stream)
        } else {
            Self.lastBody = request.httpBody
        }

        guard let handler = Self.handler else {
            client?.urlProtocol(
                self, didFailWithError: URLError(.notConnectedToInternet)
            )
            return
        }
        let (response, data) = handler(request)
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}

    private static func read(_ stream: InputStream) -> Data {
        stream.open()
        defer { stream.close() }
        var data = Data()
        let bufferSize = 4096
        let buffer = UnsafeMutablePointer<UInt8>.allocate(capacity: bufferSize)
        defer { buffer.deallocate() }
        while stream.hasBytesAvailable {
            let read = stream.read(buffer, maxLength: bufferSize)
            guard read > 0 else { break }
            data.append(buffer, count: read)
        }
        return data
    }
}
