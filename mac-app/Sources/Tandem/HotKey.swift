import AppKit
import Carbon

/// A global hotkey via Carbon's RegisterEventHotKey (works without Accessibility
/// permission, unlike NSEvent global monitors). One shared Carbon event handler
/// dispatches to per-id Swift closures.
final class HotKey {
    private var ref: EventHotKeyRef?
    private let id: UInt32

    private static var handlers: [UInt32: () -> Void] = [:]
    private static var nextId: UInt32 = 1
    private static var installed = false

    init(keyCode: UInt32, modifiers: UInt32, handler: @escaping () -> Void) {
        id = HotKey.nextId
        HotKey.nextId += 1
        HotKey.handlers[id] = handler
        HotKey.installSharedHandler()

        let hotKeyID = EventHotKeyID(signature: fourCharCode("TDM1"), id: id)
        RegisterEventHotKey(keyCode, modifiers, hotKeyID, GetEventDispatcherTarget(), 0, &ref)
    }

    private static func installSharedHandler() {
        guard !installed else { return }
        installed = true
        var spec = EventTypeSpec(
            eventClass: OSType(kEventClassKeyboard),
            eventKind: UInt32(kEventHotKeyPressed)
        )
        // The callback is a C function pointer — it captures nothing and reads
        // only static state, so it converts cleanly.
        InstallEventHandler(GetEventDispatcherTarget(), { _, event, _ -> OSStatus in
            var hkID = EventHotKeyID()
            GetEventParameter(
                event, EventParamName(kEventParamDirectObject),
                EventParamType(typeEventHotKeyID), nil,
                MemoryLayout<EventHotKeyID>.size, nil, &hkID
            )
            if let handler = HotKey.handlers[hkID.id] {
                DispatchQueue.main.async { handler() }
            }
            return noErr
        }, 1, &spec, nil, nil)
    }
}

func fourCharCode(_ string: String) -> OSType {
    var result: OSType = 0
    for byte in string.utf8.prefix(4) {
        result = (result << 8) + OSType(byte)
    }
    return result
}
