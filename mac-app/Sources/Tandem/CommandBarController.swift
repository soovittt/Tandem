import AppKit
import Combine
import SwiftUI

/// A borderless panel must opt in to becoming key to accept text input.
final class KeyablePanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

/// Hosts the SwiftUI command bar in a floating panel and resizes the panel to fit
/// the SwiftUI content (compact when empty → taller as the conversation grows),
/// anchored by its top edge.
final class CommandBarController {
    let model = ChatModel()
    private let panel: KeyablePanel
    private let hosting: NSHostingView<CommandBarView>
    private var cancellable: AnyCancellable?

    init() {
        hosting = NSHostingView(rootView: CommandBarView(model: model, onEscape: {}))
        panel = KeyablePanel(
            contentRect: NSRect(x: 0, y: 0, width: 640, height: 74),
            styleMask: [.borderless, .nonactivatingPanel, .fullSizeContentView],
            backing: .buffered, defer: false
        )
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false  // SwiftUI draws the shadow
        panel.isMovableByWindowBackground = true
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.contentView = hosting

        // Now that self exists, give the view a real escape handler.
        hosting.rootView = CommandBarView(model: model, onEscape: { [weak self] in self?.hide() })

        cancellable = model.objectWillChange.sink { [weak self] in
            DispatchQueue.main.async { self?.resize() }
        }
        resize()
    }

    func toggle() { panel.isVisible ? hide() : show() }

    func show() {
        reposition()
        panel.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        model.focusPing += 1
    }

    func hide() { panel.orderOut(nil) }

    // MARK: sizing
    private func resize() {
        hosting.layoutSubtreeIfNeeded()
        let fitting = hosting.fittingSize
        let newHeight = max(74, fitting.height)
        var frame = panel.frame
        let top = frame.origin.y + frame.size.height
        frame.size = NSSize(width: 640, height: newHeight)
        frame.origin.y = top - newHeight
        panel.setFrame(frame, display: true, animate: false)
    }

    private func reposition() {
        guard let screen = NSScreen.main else { return }
        resize()
        let frame = panel.frame
        let desiredTop = screen.frame.minY + screen.frame.height * 0.80
        let x = screen.frame.midX - frame.width / 2
        panel.setFrameOrigin(NSPoint(x: x, y: desiredTop - frame.size.height))
    }
}
