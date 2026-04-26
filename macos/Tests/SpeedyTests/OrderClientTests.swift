import Foundation
import XCTest

@testable import Speedy

/// Mirrors `SearchClientTests` patterns. We use the same `StubURLProtocol`
/// (defined there) since both clients run through `URLSession`.
final class OrderClientTests: XCTestCase {
    private var session: URLSession!

    override func setUp() {
        super.setUp()
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        session = URLSession(configuration: config)
    }

    override func tearDown() {
        StubURLProtocol.handler = nil
        StubURLProtocol.lastBody = nil
        super.tearDown()
    }

    private func client() -> HTTPOrderClient {
        HTTPOrderClient(baseURL: URL(string: "http://test.local")!, session: session)
    }

    private let request = OrderRequest(
        marketId: "m1", outcome: .yes, sizeUsdc: 5.0, side: .buy
    )

    // MARK: - Happy path

    func test_success_decodesOrderResponse() async throws {
        StubURLProtocol.handler = { _ in
            let json = #"""
            {
              "order_id": "abc-123",
              "status": "matched",
              "transaction_hash": "0xfeedface",
              "error": null
            }
            """#
            return (
                HTTPURLResponse(url: URL(string: "http://test.local/order")!,
                                statusCode: 200, httpVersion: nil, headerFields: nil)!,
                Data(json.utf8)
            )
        }

        let resp = try await client().placeOrder(request)
        XCTAssertEqual(resp.orderId, "abc-123")
        XCTAssertEqual(resp.status, "matched")
        XCTAssertEqual(resp.transactionHash, "0xfeedface")
        XCTAssertNil(resp.error)
    }

    func test_request_serializesSnakeCaseAndPostsToOrder() async throws {
        var captured: URLRequest?
        StubURLProtocol.handler = { req in
            captured = req
            let json = #"{"order_id": "x", "status": "ok", "transaction_hash": null, "error": null}"#
            return (
                HTTPURLResponse(url: req.url!,
                                statusCode: 200, httpVersion: nil, headerFields: nil)!,
                Data(json.utf8)
            )
        }

        _ = try await client().placeOrder(request)
        let request = try XCTUnwrap(captured)
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/order")

        let body = try XCTUnwrap(StubURLProtocol.lastBody)
        let parsed = try JSONSerialization.jsonObject(with: body) as? [String: Any]
        XCTAssertEqual(parsed?["market_id"] as? String, "m1")
        XCTAssertEqual(parsed?["outcome"] as? String, "Yes")
        XCTAssertEqual(parsed?["size_usdc"] as? Double, 5.0)
        XCTAssertEqual(parsed?["side"] as? String, "BUY")
    }

    // MARK: - Error surfaces

    func test_503_throwsCredentialsMissingWithDetail() async {
        StubURLProtocol.handler = { _ in
            let json = #"{"detail": "POLYMARKET_PRIVATE_KEY is not set."}"#
            return (
                HTTPURLResponse(url: URL(string: "http://test.local/order")!,
                                statusCode: 503, httpVersion: nil, headerFields: nil)!,
                Data(json.utf8)
            )
        }

        do {
            _ = try await client().placeOrder(request)
            XCTFail("expected throw")
        } catch let OrderError.credentialsMissing(message) {
            XCTAssertTrue(message.contains("POLYMARKET_PRIVATE_KEY"))
        } catch {
            XCTFail("wrong error: \(error)")
        }
    }

    func test_422_throwsHttpWithDetail() async {
        StubURLProtocol.handler = { _ in
            let json = #"{"detail": "market is not active"}"#
            return (
                HTTPURLResponse(url: URL(string: "http://test.local/order")!,
                                statusCode: 422, httpVersion: nil, headerFields: nil)!,
                Data(json.utf8)
            )
        }

        do {
            _ = try await client().placeOrder(request)
            XCTFail("expected throw")
        } catch let OrderError.http(status, message) {
            XCTAssertEqual(status, 422)
            XCTAssertEqual(message, "market is not active")
        } catch {
            XCTFail("wrong error: \(error)")
        }
    }

    func test_200_with_error_field_throwsRejected() async {
        // Backend signaled CLOB rejection via the `error` field, not a 5xx —
        // that's the path for "insufficient USDC" / "no liquidity".
        StubURLProtocol.handler = { _ in
            let json = #"""
            {
              "order_id": null,
              "status": "error",
              "transaction_hash": null,
              "error": "insufficient USDC balance"
            }
            """#
            return (
                HTTPURLResponse(url: URL(string: "http://test.local/order")!,
                                statusCode: 200, httpVersion: nil, headerFields: nil)!,
                Data(json.utf8)
            )
        }

        do {
            _ = try await client().placeOrder(request)
            XCTFail("expected throw")
        } catch let OrderError.rejected(message) {
            XCTAssertEqual(message, "insufficient USDC balance")
        } catch {
            XCTFail("wrong error: \(error)")
        }
    }

    func test_decodeFailure_throwsDecodeError() async {
        StubURLProtocol.handler = { _ in
            (
                HTTPURLResponse(url: URL(string: "http://test.local/order")!,
                                statusCode: 200, httpVersion: nil, headerFields: nil)!,
                Data("not-json".utf8)
            )
        }

        do {
            _ = try await client().placeOrder(request)
            XCTFail("expected throw")
        } catch OrderError.decode {
            // ok
        } catch {
            XCTFail("wrong error: \(error)")
        }
    }

    func test_networkFailure_throwsTransport() async {
        // Set handler to nil → StubURLProtocol returns notConnectedToInternet.
        StubURLProtocol.handler = nil

        do {
            _ = try await client().placeOrder(request)
            XCTFail("expected throw")
        } catch OrderError.transport {
            // ok
        } catch {
            XCTFail("wrong error: \(error)")
        }
    }
}
