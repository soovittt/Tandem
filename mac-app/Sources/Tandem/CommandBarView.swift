import SwiftUI

/// The command bar: a compact input that grows into a conversation. SwiftUI so it
/// looks like a real product (material, bubbles, animated thinking).
struct CommandBarView: View {
    @ObservedObject var model: ChatModel
    var onEscape: () -> Void
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 0) {
            inputRow
            if let pending = model.pendingApproval {
                Divider().opacity(0.5)
                ApprovalCard(pending: pending, onApprove: model.approve, onDeny: model.deny)
            }
            if !model.messages.isEmpty {
                Divider().opacity(0.5)
                transcript
            }
        }
        .frame(width: 640)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .strokeBorder(.white.opacity(0.10), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.35), radius: 30, y: 12)
        .onExitCommand(perform: onEscape)
        .onAppear { focused = true }
        .onChange(of: model.focusPing) { _ in focused = true }
    }

    private var inputRow: some View {
        HStack(spacing: 13) {
            TandemTile(size: 26)
            TextField("Ask Tandem to do something on your Mac…", text: $model.input)
                .textFieldStyle(.plain)
                .font(.system(size: 18))
                .focused($focused)
                .onSubmit { model.submit() }
            if model.busy {
                ProgressView().controlSize(.small).scaleEffect(0.8)
            } else if !model.input.isEmpty {
                Image(systemName: "return")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(.secondary)
                    .padding(5)
                    .background(.quaternary, in: RoundedRectangle(cornerRadius: 6))
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 17)
    }

    private var transcript: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(spacing: 10) {
                    ForEach(model.messages) { message in
                        MessageRow(message: message).id(message.id)
                    }
                    if model.busy {
                        HStack { ThinkingDots(); Spacer(minLength: 0) }
                    }
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 16)
            }
            .frame(maxHeight: 360)
            .onChange(of: model.messages.count) { _ in
                if let last = model.messages.last {
                    withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                }
            }
        }
    }
}

private struct MessageRow: View {
    let message: ChatModel.Message

    var body: some View {
        HStack(alignment: .top) {
            if message.role == .user { Spacer(minLength: 56) }
            Text(message.text)
                .font(.system(size: 13.5))
                .foregroundStyle(message.role == .user ? Color.white : Color.primary)
                .textSelection(.enabled)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(
                    message.role == .user ? AnyShapeStyle(Color.accentColor) : AnyShapeStyle(Color.primary.opacity(0.06)),
                    in: RoundedRectangle(cornerRadius: 13, style: .continuous)
                )
            if message.role == .assistant { Spacer(minLength: 56) }
        }
    }
}

private struct ApprovalCard: View {
    let pending: PendingInfo
    let onApprove: () -> Void
    let onDeny: () -> Void

    /// Split the backend's "summary\n\ndetails" into its two parts for display.
    private var parts: (summary: String, detail: String?) {
        let comps = pending.description.components(separatedBy: "\n\n")
        let summary = comps.first ?? pending.description
        let detail = comps.count > 1 ? comps.dropFirst().joined(separator: "\n\n") : nil
        return (summary, detail)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack(spacing: 8) {
                Image(systemName: "exclamationmark.shield.fill").foregroundStyle(.orange)
                Text("Approve this action?").font(.system(size: 13, weight: .semibold))
                Spacer()
                Text(pending.tool)
                    .font(.system(size: 11, weight: .medium, design: .rounded))
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 7).padding(.vertical, 3)
                    .background(.quaternary, in: Capsule())
            }
            Text(parts.summary)
                .font(.system(size: 12.5))
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if let detail = parts.detail {
                Text(detail)
                    .font(.system(size: 12))
                    .foregroundStyle(.primary)
                    .textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.primary.opacity(0.05), in: RoundedRectangle(cornerRadius: 9, style: .continuous))
            }
            HStack(spacing: 10) {
                Spacer()
                Button("Deny", action: onDeny)
                // No default-action shortcut on Approve: a consequential action must
                // be an explicit click, never a reflexive Return in the text field.
                Button("Approve", action: onApprove)
                    .buttonStyle(.borderedProminent)
            }
        }
        .padding(16)
        .background(Color.orange.opacity(0.08))
    }
}

private struct ThinkingDots: View {
    @State private var active = 0

    var body: some View {
        HStack(spacing: 5) {
            ForEach(0..<3, id: \.self) { index in
                Circle()
                    .frame(width: 6, height: 6)
                    .foregroundStyle(.secondary)
                    .opacity(active == index ? 1 : 0.25)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .onAppear {
            Timer.scheduledTimer(withTimeInterval: 0.3, repeats: true) { _ in
                active = (active + 1) % 3
            }
        }
    }
}
