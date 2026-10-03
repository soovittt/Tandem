import Foundation

/// A consequential action the agent is waiting for the user to approve.
struct PendingInfo: Decodable, Equatable {
    let id: String
    let tool: String
    let description: String
}

/// One event from the streaming turn.
enum StreamEvent {
    case token(String)         // a chunk of the answer, as it generates
    case tool(String)          // a tool just started running
    case done(String, Int)     // final authoritative answer + step count
}

/// Client to the local Tandem agent backend (:8000). Streams the turn over SSE and
/// polls /pending for approvals concurrently while the stream is in flight.
final class Backend {
    static let shared = Backend()
    private let base = URL(string: "http://127.0.0.1:8000")!
    private(set) var sessionId = UUID().uuidString
    private var polling = false

    func newSession() { sessionId = UUID().uuidString }

    /// Stream a message. `onEvent` fires per token/tool/done, `onPending` when the
    /// agent needs approval; `completion` ends the turn. All callbacks on the main actor.
    func stream(
        _ message: String,
        onEvent: @escaping (StreamEvent) -> Void,
        onPending: @escaping (PendingInfo) -> Void,
        completion: @escaping (Result<Void, Error>) -> Void
    ) {
        startPolling(onPending: onPending)

        var request = URLRequest(url: base.appendingPathComponent("chat/stream"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.timeoutInterval = 300
        request.httpBody = try? JSONSerialization.data(withJSONObject: [
            "message": message, "session_id": sessionId,
        ])

        Task {
            do {
                let (bytes, response) = try await URLSession.shared.bytes(for: request)
                guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                    throw Self.err("Backend returned an error — is it running on :8000?")
                }
                for try await line in bytes.lines {
                    guard line.hasPrefix("data:"),
                          let event = Self.parse(line.dropFirst(5)) else { continue }
                    await MainActor.run { onEvent(event) }
                }
                polling = false
                await MainActor.run { completion(.success(())) }
            } catch {
                polling = false
                await MainActor.run { completion(.failure(error)) }
            }
        }
    }

    private static func parse(_ payload: Substring) -> StreamEvent? {
        let trimmed = payload.trimmingCharacters(in: .whitespaces)
        guard let data = trimmed.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = obj["type"] as? String else { return nil }
        switch type {
        case "token": return .token(obj["text"] as? String ?? "")
        case "tool": return .tool(obj["name"] as? String ?? "")
        case "done": return .done(obj["text"] as? String ?? "", obj["steps"] as? Int ?? 0)
        default: return nil  // "session" and anything else: ignore
        }
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

    /// Generic GET → decode JSON (used by the Control Center panes). Main-actor callback.
    func getJSON<T: Decodable>(_ path: String, as type: T.Type, completion: @escaping (T?) -> Void) {
        URLSession.shared.dataTask(with: base.appendingPathComponent(path)) { data, _, _ in
            let decoded = data.flatMap { try? JSONDecoder().decode(T.self, from: $0) }
            DispatchQueue.main.async { completion(decoded) }
        }.resume()
    }

    // --- WhatsApp connection (in-app QR linking) ---------------------------
    func whatsappStatus(completion: @escaping ([String: Any]?) -> Void) {
        let url = base.appendingPathComponent("whatsapp/status")
        URLSession.shared.dataTask(with: url) { data, _, _ in
            let obj = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            DispatchQueue.main.async { completion(obj) }
        }.resume()
    }

    func whatsappConnect(completion: @escaping ([String: Any]?) -> Void) {
        var request = URLRequest(url: base.appendingPathComponent("whatsapp/connect"))
        request.httpMethod = "POST"
        request.timeoutInterval = 20
        URLSession.shared.dataTask(with: request) { data, _, _ in
            let obj = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            DispatchQueue.main.async { completion(obj) }
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
