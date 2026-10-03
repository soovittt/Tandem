import AppKit
import ApplicationServices
import SwiftUI

// MARK: - Data

struct IntegrationItem: Decodable, Identifiable {
    let id: String
    let name: String
    let icon: String
    let desc: String
    let status: String
}

struct ModelInfo: Decodable {
    let model: String
    let base_url: String
    let reachable: Bool
    let reasoning: String
    let tool_mode: String
}

final class ControlCenterModel: ObservableObject {
    @Published var integrations: [IntegrationItem] = []
    @Published var modelInfo: ModelInfo?
    let whatsapp = WhatsAppModel()

    private var timer: Timer?

    func startAutoRefresh() {
        refresh()
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 3, repeats: true) { [weak self] _ in self?.refresh() }
    }

    func stopAutoRefresh() { timer?.invalidate(); timer = nil }

    func refresh() {
        Backend.shared.getJSON("integrations", as: [IntegrationItem].self) { [weak self] in
            if let items = $0 { self?.integrations = items }
        }
        Backend.shared.getJSON("model", as: ModelInfo.self) { [weak self] in self?.modelInfo = $0 }
    }
}

// MARK: - Window shell

private enum Pane: String, CaseIterable, Identifiable {
    case integrations = "Integrations"
    case model = "Model"
    case permissions = "Permissions"
    case about = "About"
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .integrations: return "square.grid.2x2.fill"
        case .model: return "cpu.fill"
        case .permissions: return "lock.shield.fill"
        case .about: return "info.circle.fill"
        }
    }
}

struct ControlCenterView: View {
    @StateObject private var model = ControlCenterModel()
    @State private var pane: Pane = .integrations

    var body: some View {
        HStack(spacing: 0) {
            sidebar
            Divider()
            ScrollView {
                detail
                    .padding(26)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .frame(width: 740, height: 520)
        .onAppear { model.startAutoRefresh() }
        .onDisappear { model.stopAutoRefresh() }
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 9) {
                TandemTile(size: 24)
                Text("Tandem").font(.system(size: 15, weight: .bold))
            }
            .padding(.horizontal, 6)
            VStack(alignment: .leading, spacing: 2) {
                ForEach(Pane.allCases) { p in
                    Button { pane = p } label: {
                        Label(p.rawValue, systemImage: p.icon)
                            .font(.system(size: 13))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 10).padding(.vertical, 7)
                            .background(pane == p ? Color.accentColor.opacity(0.18) : .clear,
                                        in: RoundedRectangle(cornerRadius: 7))
                            .foregroundStyle(pane == p ? Color.accentColor : .primary)
                    }
                    .buttonStyle(.plain)
                }
            }
            Spacer()
        }
        .padding(14)
        .frame(width: 196)
        .background(.quaternary.opacity(0.35))
    }

    @ViewBuilder private var detail: some View {
        switch pane {
        case .integrations: IntegrationsPane(model: model)
        case .model: ModelPane(model: model)
        case .permissions: PermissionsPane()
        case .about: AboutPane()
        }
    }
}

// MARK: - Panes

private struct PaneHeader: View {
    let title: String
    let subtitle: String
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.system(size: 22, weight: .bold))
            Text(subtitle).font(.system(size: 12.5)).foregroundStyle(.secondary)
        }
    }
}

private struct IntegrationsPane: View {
    @ObservedObject var model: ControlCenterModel
    @State private var showWhatsApp = false

    private var connected: [IntegrationItem] { model.integrations.filter { $0.status != "coming_soon" } }
    private var soon: [IntegrationItem] { model.integrations.filter { $0.status == "coming_soon" } }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            PaneHeader(title: "Integrations",
                       subtitle: "Connect the apps Tandem can see and act on — everything runs locally on your Mac.")
            VStack(spacing: 8) {
                ForEach(connected) { item in
                    IntegrationRow(item: item) { if item.id == "whatsapp" { showWhatsApp = true } }
                }
            }
            if !soon.isEmpty {
                Text("COMING SOON").font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(.tertiary).padding(.top, 6)
                VStack(spacing: 8) {
                    ForEach(soon) { item in IntegrationRow(item: item) {} }
                }
            }
        }
        .sheet(isPresented: $showWhatsApp) {
            WhatsAppConnectView(model: model.whatsapp) { showWhatsApp = false }
        }
    }
}

private struct IntegrationRow: View {
    let item: IntegrationItem
    var onConnect: () -> Void

    var body: some View {
        HStack(spacing: 13) {
            Image(systemName: item.icon)
                .font(.system(size: 17))
                .frame(width: 26)
                .foregroundStyle(item.status == "coming_soon" ? AnyShapeStyle(.tertiary) : AnyShapeStyle(.primary))
            VStack(alignment: .leading, spacing: 2) {
                Text(item.name).font(.system(size: 13.5, weight: .semibold))
                Text(item.desc).font(.system(size: 11.5)).foregroundStyle(.secondary).lineLimit(1)
            }
            Spacer(minLength: 10)
            trailing
        }
        .padding(.horizontal, 14).padding(.vertical, 11)
        .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 10))
        .opacity(item.status == "coming_soon" ? 0.6 : 1)
    }

    @ViewBuilder private var trailing: some View {
        switch item.status {
        case "connected", "available": pill("Connected", .green)
        case "linking": pill("Linking…", .orange)
        case "disconnected":
            Button("Connect", action: onConnect).controlSize(.small).buttonStyle(.borderedProminent)
        case "coming_soon": pill("Soon", .secondary)
        default: pill(item.status.capitalized, .secondary)
        }
    }

    private func pill(_ text: String, _ color: Color) -> some View {
        Text(text)
            .font(.system(size: 11, weight: .medium))
            .foregroundStyle(color)
            .padding(.horizontal, 9).padding(.vertical, 4)
            .background(color.opacity(0.15), in: Capsule())
    }
}

private struct ModelPane: View {
    @ObservedObject var model: ControlCenterModel
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            PaneHeader(title: "Model", subtitle: "The brain powering Tandem.")
            if let info = model.modelInfo {
                card {
                    row("Model", info.model)
                    row("Endpoint", info.base_url)
                    HStack {
                        Text("Status").foregroundStyle(.secondary).frame(width: 120, alignment: .leading)
                        Circle().fill(info.reachable ? Color.green : Color.red).frame(width: 8, height: 8)
                        Text(info.reachable ? "Reachable" : "Unreachable")
                    }.font(.system(size: 12.5))
                    row("Tool calling", info.tool_mode)
                    row("Reasoning", info.reasoning)
                }
            } else {
                ProgressView().controlSize(.small)
            }
        }
    }
    private func card<C: View>(@ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 10) { content() }
            .padding(16).frame(maxWidth: .infinity, alignment: .leading)
            .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 10))
    }
    private func row(_ k: String, _ v: String) -> some View {
        HStack(alignment: .top) {
            Text(k).foregroundStyle(.secondary).frame(width: 120, alignment: .leading)
            Text(v).textSelection(.enabled)
        }.font(.system(size: 12.5))
    }
}

private struct PermissionsPane: View {
    @State private var accessibility = AXIsProcessTrusted()
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            PaneHeader(title: "Permissions",
                       subtitle: "Tandem controls your Mac through macOS permissions. Grant these for full control.")
            permissionRow(
                "Accessibility", "Needed to minimize/hide windows and control any app.",
                granted: accessibility, settings: "Privacy_Accessibility")
            permissionRow(
                "Automation", "Needed to drive Apple apps (Calendar, Notes, Messages…). macOS prompts the first time.",
                granted: nil, settings: "Privacy_Automation")
            Button("Re-check") { accessibility = AXIsProcessTrusted() }
                .controlSize(.small).padding(.top, 4)
        }
    }
    private func permissionRow(_ title: String, _ desc: String, granted: Bool?, settings: String) -> some View {
        HStack(spacing: 13) {
            Image(systemName: granted == true ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                .foregroundStyle(granted == true ? .green : .orange).frame(width: 24)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.system(size: 13.5, weight: .semibold))
                Text(desc).font(.system(size: 11.5)).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 10)
            Button("Open Settings") {
                if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?\(settings)") {
                    NSWorkspace.shared.open(url)
                }
            }.controlSize(.small)
        }
        .padding(14).background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 10))
    }
}

private struct AboutPane: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            PaneHeader(title: "About Tandem", subtitle: "Your private AI that lives on your Mac.")
            HStack(spacing: 14) {
                TandemTile(size: 52)
                VStack(alignment: .leading, spacing: 3) {
                    Text("Tandem").font(.system(size: 17, weight: .bold))
                    Text("Version 0.1").font(.system(size: 12)).foregroundStyle(.secondary)
                }
            }
            VStack(alignment: .leading, spacing: 8) {
                Label("Summon anywhere with ⌥Space", systemImage: "command")
                Label("Controls your Mac + apps, with approval for anything consequential", systemImage: "hand.raised.fill")
                Label("Runs on an NVIDIA Nemotron model — your data stays on your machine", systemImage: "lock.fill")
            }
            .font(.system(size: 12.5)).foregroundStyle(.secondary)
            .padding(16).frame(maxWidth: .infinity, alignment: .leading)
            .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 10))
        }
    }
}

// MARK: - Window controller

final class ControlCenterController {
    private var window: NSWindow?

    func show() {
        if let window {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            return
        }
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 740, height: 520),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered, defer: false
        )
        window.title = "Tandem"
        window.contentView = NSHostingView(rootView: ControlCenterView())
        window.isReleasedWhenClosed = false
        window.center()
        self.window = window
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
