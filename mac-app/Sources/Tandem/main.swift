import AppKit
import Carbon

/// Menu-bar status item with Open / Quit.
final class StatusBarController: NSObject {
    private let item: NSStatusItem
    private let onOpen: () -> Void

    init(onOpen: @escaping () -> Void) {
        self.onOpen = onOpen
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        super.init()
        if let button = item.button {
            button.image = tandemMenuBarImage()
        }
        let menu = NSMenu()
        let open = NSMenuItem(title: "Open Tandem  (⌥Space)", action: #selector(openCommandBar), keyEquivalent: "")
        open.target = self
        menu.addItem(open)
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "Quit Tandem", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        item.menu = menu
    }

    @objc private func openCommandBar() { onOpen() }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private let commandBar = CommandBarController()
    private var hotKey: HotKey?
    private var statusBar: StatusBarController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)  // menu-bar only, no dock icon
        installEditMenu()  // enables ⌘C/⌘V/⌘X/⌘A/⌘Z in the command bar text field
        statusBar = StatusBarController { [weak self] in self?.commandBar.show() }
        // ⌥Space toggles the command bar.
        hotKey = HotKey(keyCode: UInt32(kVK_Space), modifiers: UInt32(optionKey)) { [weak self] in
            self?.commandBar.toggle()
        }
    }

    /// A menu-bar-only app has no main menu, so the standard editing shortcuts
    /// (⌘C/⌘V/⌘X/⌘A/⌘Z) have no key equivalents to fire `paste:` & friends on the
    /// focused text field. Installing an Edit menu wires them through the responder
    /// chain. `target == nil` means "dispatch to whoever is first responder".
    private func installEditMenu() {
        let mainMenu = NSMenu()
        let editItem = NSMenuItem()
        mainMenu.addItem(editItem)
        let editMenu = NSMenu(title: "Edit")
        editItem.submenu = editMenu

        func add(_ title: String, _ selector: Selector, _ key: String,
                 _ mods: NSEvent.ModifierFlags = .command) {
            let item = NSMenuItem(title: title, action: selector, keyEquivalent: key)
            item.keyEquivalentModifierMask = mods
            item.target = nil
            editMenu.addItem(item)
        }
        add("Undo", Selector(("undo:")), "z")
        add("Redo", Selector(("redo:")), "z", [.command, .shift])
        editMenu.addItem(.separator())
        add("Cut", Selector(("cut:")), "x")
        add("Copy", Selector(("copy:")), "c")
        add("Paste", Selector(("paste:")), "v")
        add("Select All", Selector(("selectAll:")), "a")

        NSApp.mainMenu = mainMenu
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
