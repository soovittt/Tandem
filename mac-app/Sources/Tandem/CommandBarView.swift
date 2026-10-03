import SwiftUI

private let brandGradient = LinearGradient(
    colors: [Color(hex: 0x6366F1), Color(hex: 0xA855F7)],
    startPoint: .topLeading, endPoint: .bottomTrailing
)

/// The command bar: a compact input that grows into a conversation. Tuned to feel
/// like a real product — glassy panel, markdown answers, gradient bubbles.
struct CommandBarView: View {
    @ObservedObject var model: ChatModel
    var onEscape: () -> Void
    @FocusState private var focused: Bool

    private let suggestions = ["What's on my calendar today?", "Open Spotify", "Summarize my unread emails"]

    var body: some View {
        VStack(spacing: 0) {
            inputRow
            if let pending = model.pendingApproval {
                divider
                ApprovalCard(pending: pending, onApprove: model.approve, onDeny: model.deny)
            }
            if !model.messages.isEmpty {
                divider
                transcript
            } else if model.input.isEmpty && !model.busy {
                suggestionRow
            }
        }
        .frame(width: 680)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .strokeBorder(
                    LinearGradient(colors: [.white.opacity(0.16), .white.opacity(0.04)],
                                   startPoint: .top, endPoint: .bottom),
                    lineWidth: 1
                )
        )
        .shadow(color: .black.opacity(0.40), radius: 40, y: 18)
        .onExitCommand(perform: onEscape)
        .onAppear { focused = true }
        .onChange(of: model.focusPing) { _ in focused = true }
    }

    private var divider: some View {
        Rectangle().fill(.white.opacity(0.08)).frame(height: 1)
    }

    private var inputRow: some View {
        HStack(spacing: 13) {
            TandemTile(size: 30)
            TextField("Ask Tandem anything…", text: $model.input)
                .textFieldStyle(.plain)
                .font(.system(size: 18, weight: .regular))
                .focused($focused)
                .onSubmit { model.submit() }

            if !model.messages.isEmpty && !model.busy {
                Button { model.clear(); model.focusPing += 1 } label: {
                    Image(systemName: "square.and.pencil").font(.system(size: 15, weight: .medium))
                }
                .buttonStyle(.plain).foregroundStyle(.secondary).help("New chat")
            }
            if model.busy {
                ProgressView().controlSize(.small).scaleEffect(0.85)
            } else if !model.input.isEmpty {
                Button(action: model.submit) {
                    Image(systemName: "arrow.up")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundStyle(.white)
                        .frame(width: 26, height: 26)
                        .background(brandGradient, in: Circle())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 15)
    }

    private var suggestionRow: some View {
        HStack(spacing: 8) {
            ForEach(suggestions, id: \.self) { s in
                Button { model.input = s; focused = true } label: {
                    Text(s)
                        .font(.system(size: 11.5))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .background(.white.opacity(0.06), in: Capsule())
                        .overlay(Capsule().strokeBorder(.white.opacity(0.07), lineWidth: 1))
                }
                .buttonStyle(.plain)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 18)
        .padding(.bottom, 15)
    }

    private var transcript: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    ForEach(model.messages) { message in
                        MessageRow(message: message).id(message.id)
                    }
                    if model.busy, model.messages.last?.role != .assistant {
                        HStack(alignment: .top, spacing: 10) {
                            TandemTile(size: 22)
                            ThinkingDots()
                            Spacer(minLength: 0)
                        }
                    }
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 16)
            }
            .frame(maxHeight: 400)
            .onChange(of: model.messages.count) { _ in scrollToEnd(proxy) }
            .onChange(of: model.messages.last?.text) { _ in scrollToEnd(proxy) }
        }
    }

    private func scrollToEnd(_ proxy: ScrollViewProxy) {
        if let last = model.messages.last {
            withAnimation(.easeOut(duration: 0.15)) { proxy.scrollTo(last.id, anchor: .bottom) }
        }
    }
}

/// One turn. User = right-aligned gradient bubble; assistant = avatar + clean
/// markdown text (no heavy bubble, so long answers and bullet lists read well).
private struct MessageRow: View {
    let message: ChatModel.Message

    var body: some View {
        if message.role == .user {
            HStack {
                Spacer(minLength: 60)
                Text(message.text)
                    .font(.system(size: 14))
                    .foregroundStyle(.white)
                    .textSelection(.enabled)
                    .padding(.horizontal, 13).padding(.vertical, 9)
                    .background(brandGradient, in: RoundedRectangle(cornerRadius: 15, style: .continuous))
            }
        } else {
            HStack(alignment: .top, spacing: 10) {
                TandemTile(size: 22)
                MarkdownText(text: message.text)
                    .font(.system(size: 14))
                    .foregroundStyle(.primary)
                    .textSelection(.enabled)
                    .padding(.top, 1)
                Spacer(minLength: 24)
            }
        }
    }
}

/// Lightweight markdown: inline **bold**/*italic*/`code` everywhere, plus proper
/// bullets for `* ` / `- ` lines. Enough to make model answers look clean.
private struct MarkdownText: View {
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            ForEach(Array(text.components(separatedBy: "\n").enumerated()), id: \.offset) { _, line in
                lineView(line)
            }
        }
    }

    @ViewBuilder private func lineView(_ raw: String) -> some View {
        let trimmed = raw.trimmingCharacters(in: .whitespaces)
        if trimmed.hasPrefix("* ") || trimmed.hasPrefix("- ") {
            HStack(alignment: .top, spacing: 8) {
                Text("•").foregroundStyle(.secondary)
                Text(inline(String(trimmed.dropFirst(2))))
            }
        } else if trimmed.isEmpty {
            Color.clear.frame(height: 3)
        } else {
            Text(inline(raw))
        }
    }

    private func inline(_ s: String) -> AttributedString {
        (try? AttributedString(
            markdown: s,
            options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        )) ?? AttributedString(s)
    }
}

private struct ApprovalCard: View {
    let pending: PendingInfo
    let onApprove: () -> Void
    let onDeny: () -> Void

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
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(.white.opacity(0.08), in: Capsule())
            }
            Text(parts.summary)
                .font(.system(size: 12.5)).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if let detail = parts.detail {
                Text(detail)
                    .font(.system(size: 12.5)).foregroundStyle(.primary)
                    .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                    .padding(11).frame(maxWidth: .infinity, alignment: .leading)
                    .background(.white.opacity(0.05), in: RoundedRectangle(cornerRadius: 9, style: .continuous))
            }
            HStack(spacing: 10) {
                Spacer()
                Button("Deny", action: onDeny).controlSize(.large)
                Button("Approve", action: onApprove).controlSize(.large).buttonStyle(.borderedProminent)
            }
        }
        .padding(16)
        .background(Color.orange.opacity(0.09))
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
                    .scaleEffect(active == index ? 1.1 : 0.9)
            }
        }
        .padding(.vertical, 6)
        .onAppear {
            Timer.scheduledTimer(withTimeInterval: 0.28, repeats: true) { _ in
                withAnimation(.easeInOut(duration: 0.2)) { active = (active + 1) % 3 }
            }
        }
    }
}
