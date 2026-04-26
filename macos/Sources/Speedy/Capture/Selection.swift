import Foundation

/// What the capture layer hands back to the rest of the app — the input to
/// the `/search` request and (eventually) the overlay's title.
///
/// `surroundingContext` and `pageTitle` are both optional because the
/// pasteboard fallback can only recover the highlight itself; the AX path
/// usually fills both in.
struct Selection: Equatable {
    enum Source: String {
        case accessibility
        case pasteboard
    }

    let highlight: String
    let surroundingContext: String?
    let pageTitle: String?
    let source: Source
}
