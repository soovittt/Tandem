import Foundation

struct ChatResponse: Decodable {
    let session_id: String
    let text: String
    let steps: Int
}

/// A consequential action the agent is waiting for the user to approve.
struct PendingInfo: Decodable, Equatable {
    let id: String
    let tool: String
    let description: String
}

/// Client to the local Tandem agent backend (:8000). Owns a stable session id so
/// it can poll /pending for approvals while the long /chat request is in flight.
final class Backend {
    static let shared = Backend()
    private let base = URL(string: "http://127.0.0.1:8000")!
    private(set) var sessionId = UUID().uuidString
    private var polling = false

    func newSession() { sessionId = UUID().uuidString }

    /// Send a message. `onPending` fires (on main) when the agent needs approval.
    func send(
        _ message: String,
        onPending: @escaping (PendingInfo) -> Void,
        completion: @escaping (Result<String, Error>) -> Void
    ) {
        startPolling(onPending: onPending)

        var request = URLRequest(url: base.appendingPathComponent("chat"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 300
        request.httpBody = try? JSONSerialization.data(withJSONObject: [
            "message": message, "session_id": sessionId,
        ])

        URLSession.shared.dataTask(with: request) { [weak self] data, _, error in
            self?.polling = false
            if let error { completion(.failure(error)); return }
            guard let data else {
                completion(.failure(Self.err("No response — is the backend running on :8000?")))
                return
            }
            do {
                let decoded = try JSONDecoder().decode(ChatResponse.self, from: data)
                completion(.success(decoded.text))
            } catch {
                let raw = String(data: data, encoding: .utf8) ?? "?"
                completion(.failure(Self.err("Bad response: \(raw.prefix(180))")))
            }
        }.resume()
    }

    /// Approve or deny a SPECIFIC pending action (by id). completion(true) only if
    /// the server honored it; otherwise the caller can restore the card.
    func resolve(id: String, approved: Bool, completion: @escaping (Bool) -> Void) {
        var request = URLRequest(url: base.appendingPathComponent("approve/\(sessionId)"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["id": id, "approved": approved])
        URLSession.shared.dataTask(with: request) { data, _, error in
            var ok = false
            if error == nil, let data,
               let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Bool] {
                ok = obj["ok"] ?? false
            }
            DispatchQueue.main.async { completion(ok) }
        }.resume()
    }

    private func startPolling(onPending: @escaping (PendingInfo) -> Void) {
        polling = true
        var lastShown: PendingInfo?
        func poll() {
            guard polling else { return }
            let url = base.appendingPathComponent("pending/\(sessionId)")
            URLSession.shared.dataTask(with: url) { [weak self] data, _, _ in
                guard let self else { return }
                if let data {
                    if let p = try? JSONDecoder().decode(PendingInfo.self, from: data) {
                        // Only surface while the turn is live, and only new actions.
                        if p != lastShown && self.polling {
                            lastShown = p
                            DispatchQueue.main.async { onPending(p) }
                        }
                    } else {
                        lastShown = nil  // null → no pending; let a repeat re-show
                    }
                }
                if self.polling {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5, execute: poll)
                }
            }.resume()
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5, execute: poll)
    }

    private static func err(_ message: String) -> NSError {
        NSError(domain: "tandem", code: 1, userInfo: [NSLocalizedDescriptionKey: message])
    }
}
