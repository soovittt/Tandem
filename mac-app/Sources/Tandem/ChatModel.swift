import SwiftUI

/// Observable conversation state for the command bar.
final class ChatModel: ObservableObject {
    struct Message: Identifiable {
        enum Role { case user, assistant }
        let id = UUID()
        let role: Role
        var text: String
    }

    @Published var messages: [Message] = []
    @Published var input = ""
    @Published var busy = false
    @Published var pendingApproval: PendingInfo?
    @Published var focusPing = 0  // bumped to re-focus the field when summoned

    init() { restore() }

    /// Load the persisted conversation so the chat continues where it left off.
    func restore() {
        Backend.shared.fetchConversation { [weak self] turns in
            guard let self, self.messages.isEmpty else { return }
            self.messages = turns.map {
                Message(role: $0.role == "user" ? .user : .assistant, text: $0.text)
            }
        }
    }

    func submit() {
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !busy else { return }
        input = ""
        messages.append(Message(role: .user, text: text))
        busy = true

        // The assistant bubble appears on the first token and fills as they arrive;
        // the `done` event replaces it with the authoritative (cleaned) answer.
        var assistantId: UUID?
        var streamed = ""

        Backend.shared.stream(
            text,
            onEvent: { [weak self] event in
                guard let self else { return }
                switch event {
                case .token(let chunk):
                    streamed += chunk
                    if let id = assistantId {
                        self.setText(id, streamed)
                    } else {
                        let bubble = Message(role: .assistant, text: streamed)
                        assistantId = bubble.id
                        self.messages.append(bubble)
                    }
                case .tool:
                    break  // a tool is running; the thinking indicator covers it
                case .done(let finalText, _):
                    if let id = assistantId {
                        self.setText(id, finalText)
                    } else {
                        self.messages.append(Message(role: .assistant, text: finalText))
                    }
                }
            },
            onPending: { [weak self] pending in
                self?.pendingApproval = pending
            },
            completion: { [weak self] result in
                guard let self else { return }
                self.busy = false
                self.pendingApproval = nil
                if case .failure(let error) = result, assistantId == nil {
                    self.messages.append(Message(role: .assistant, text: "⚠️ \(error.localizedDescription)"))
                }
            }
        )
    }

    private func setText(_ id: UUID, _ text: String) {
        if let i = messages.firstIndex(where: { $0.id == id }) {
            messages[i].text = text
        }
    }

    func approve() { resolve(approved: true) }
    func deny() { resolve(approved: false) }

    private func resolve(approved: Bool) {
        guard let pending = pendingApproval else { return }
        pendingApproval = nil  // optimistic
        Backend.shared.resolve(id: pending.id, approved: approved) { [weak self] ok in
            if !ok { self?.pendingApproval = pending }  // restore so the user can retry
        }
    }

    func clear() {
        guard !busy else { return }  // don't desync an in-flight turn
        messages = []
        input = ""
        pendingApproval = nil
        Backend.shared.newSession()
    }
}
