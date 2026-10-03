import AppKit
import CoreImage.CIFilterBuiltins
import SwiftUI

/// Drives the in-app WhatsApp linking flow: start the bridge, poll status, surface
/// the QR + connected state. No terminal — the user scans once, in the app.
final class WhatsAppModel: ObservableObject {
    @Published var qr: String?
    @Published var connected = false
    @Published var starting = true

    private var timer: Timer?

    func start() {
        starting = true
        connected = false
        qr = nil
        Backend.shared.whatsappConnect { [weak self] _ in self?.starting = false }
        poll()
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { [weak self] _ in self?.poll() }
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }

    private func poll() {
        Backend.shared.whatsappStatus { [weak self] obj in
            guard let self, let obj else { return }
            self.connected = (obj["connected"] as? Bool) ?? false
            self.qr = obj["qr"] as? String
            if self.connected { self.stop() }  // linked — stop polling
        }
    }
}

struct WhatsAppConnectView: View {
    @ObservedObject var model: WhatsAppModel
    var onClose: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            HStack(spacing: 8) {
                Image(systemName: "bubble.left.and.bubble.right.fill").foregroundStyle(.green)
                Text("Connect WhatsApp").font(.system(size: 15, weight: .semibold))
                Spacer()
                Button(action: onClose) { Image(systemName: "xmark.circle.fill").foregroundStyle(.secondary) }
                    .buttonStyle(.plain)
            }

            if model.connected {
                VStack(spacing: 10) {
                    Image(systemName: "checkmark.circle.fill").font(.system(size: 46)).foregroundStyle(.green)
                    Text("Connected").font(.system(size: 14, weight: .semibold))
                    Text("WhatsApp is linked. You can close this window.")
                        .font(.system(size: 12)).foregroundStyle(.secondary).multilineTextAlignment(.center)
                }.padding(.vertical, 22)
            } else if let qr = model.qr, let image = Self.qrImage(qr) {
                Image(nsImage: image).interpolation(.none).resizable()
                    .frame(width: 220, height: 220)
                    .background(Color.white)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                Text("On your phone: **WhatsApp → Settings → Linked Devices → Link a Device**, then scan this.")
                    .font(.system(size: 12)).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                ProgressView().controlSize(.small).padding(.vertical, 38)
                Text(model.starting ? "Starting WhatsApp…" : "Waiting for the QR code…")
                    .font(.system(size: 12)).foregroundStyle(.secondary)
            }
        }
        .padding(20)
        .frame(width: 300)
        .onAppear { model.start() }
        .onDisappear { model.stop() }
    }

    /// Render the pairing string as a crisp QR image (CoreImage).
    static func qrImage(_ string: String) -> NSImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(string.utf8)
        filter.correctionLevel = "M"
        guard let output = filter.outputImage?.transformed(by: CGAffineTransform(scaleX: 10, y: 10)) else {
            return nil
        }
        let rep = NSCIImageRep(ciImage: output)
        let image = NSImage(size: rep.size)
        image.addRepresentation(rep)
        return image
    }
}

/// Owns the Connect WhatsApp window (shown from the menu bar or just-in-time).
final class WhatsAppConnectController {
    private var window: NSWindow?
    private let model = WhatsAppModel()

    func show() {
        if let window {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            return
        }
        let view = WhatsAppConnectView(model: model, onClose: { [weak self] in self?.window?.close() })
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 300, height: 380),
            styleMask: [.titled, .closable],
            backing: .buffered, defer: false
        )
        window.title = "Connect WhatsApp"
        window.contentView = NSHostingView(rootView: view)
        window.isReleasedWhenClosed = false
        window.center()
        self.window = window
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
