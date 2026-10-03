import SwiftUI

/// Observable conversation state for the command bar.
final class ChatModel: ObservableObject {
    struct Message: Identifiable {
        enum Role { case user, assistant }
        let id = UUID()
        let role: Role
        var text: String
        var tools: [String] = []  // tools used to produce this assistant turn
    }

    @Published var messages: [Message] = []
    @Published var input = ""
    @Published var busy = false
    @Published var pendingApproval: PendingInfo?
    @Published var focusPing = 0  // bumped to re-focus the field when summoned
    @Published var history: [(id: String, title: String)] = []

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

    func loadHistory() {
        Backend.shared.fetchConversations { [weak self] in self?.history = $0 }
    }

    /// Open a past chat from history.
    func switchTo(_ id: String) {
        guard !busy else { return }
        Backend.shared.setSession(id)
        messages = []
        pendingApproval = nil
        restore()
    }

    func submit() {
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !busy else { return }
        input = ""
        messages.append(Message(role: .user, text: text))
        busy = true

        // The assistant bubble appears on the first tool or token and fills in; tool
        // events are shown as badges, and `done` sets the authoritative final text.
        var assistantId: UUID?
        var streamed = ""
        var toolsUsed: [String] = []

        func ensureAssistant() -> UUID {
            if let id = assistantId { return id }
            let bubble = Message(role: .assistant, text: streamed, tools: toolsUsed)
            assistantId = bubble.id
            messages.append(bubble)
            return bubble.id
        }

        Backend.shared.stream(
            text,
            onEvent: { [weak self] event in
                guard let self else { return }
                switch event {
                case .tool(let name):
                    toolsUsed.append(name)
                    self.setTools(ensureAssistant(), toolsUsed)
                case .token(let chunk):
                    streamed += chunk
                    self.setText(ensureAssistant(), streamed)
                case .done(let finalText, _):
                    let id = ensureAssistant()
                    self.setText(id, finalText)
                    self.setTools(id, toolsUsed)
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
        if let i = messages.firstIndex(where: { $0.id == id }) { messages[i].text = text }
    }

    private func setTools(_ id: UUID, _ tools: [String]) {
        if let i = messages.firstIndex(where: { $0.id == id }) { messages[i].tools = tools }
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
