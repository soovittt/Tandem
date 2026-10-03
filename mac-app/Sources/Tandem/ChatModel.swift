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

    func submit() {
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !busy else { return }
        input = ""
        messages.append(Message(role: .user, text: text))
        busy = true

        Backend.shared.send(
            text,
            onPending: { [weak self] pending in
                self?.pendingApproval = pending
            },
            completion: { [weak self] result in
                DispatchQueue.main.async {
                    guard let self else { return }
                    self.busy = false
                    self.pendingApproval = nil
                    switch result {
                    case .success(let reply):
                        self.messages.append(Message(role: .assistant, text: reply))
                    case .failure(let error):
                        self.messages.append(Message(role: .assistant, text: "⚠️ \(error.localizedDescription)"))
                    }
                }
            }
        )
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
