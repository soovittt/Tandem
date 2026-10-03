import AppKit
import SwiftUI

extension Color {
    init(hex: UInt) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xff) / 255,
            green: Double((hex >> 8) & 0xff) / 255,
            blue: Double(hex & 0xff) / 255
        )
    }
}

/// The Tandem glyph: two rounded chevrons in sync — "two moving together."
/// Drawn in a unit square (0...1) so it scales to any size; meant to be stroked.
struct TandemGlyph: Shape {
    func path(in rect: CGRect) -> Path {
        let s = min(rect.width, rect.height)
        let ox = rect.midX - s / 2
        let oy = rect.midY - s / 2
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: ox + x * s, y: oy + y * s) }
        var path = Path()
        path.move(to: p(0.30, 0.22)); path.addLine(to: p(0.52, 0.50)); path.addLine(to: p(0.30, 0.78))
        path.move(to: p(0.52, 0.22)); path.addLine(to: p(0.74, 0.50)); path.addLine(to: p(0.52, 0.78))
        return path
    }
}

/// The app-icon tile: indigo→violet squircle with the white glyph. Used in the
/// command bar and as the app/brand mark.
struct TandemTile: View {
    var size: CGFloat
    var body: some View {
        RoundedRectangle(cornerRadius: size * 0.28, style: .continuous)
            .fill(
                LinearGradient(
                    colors: [Color(hex: 0x6366F1), Color(hex: 0xA855F7)],
                    startPoint: .topLeading, endPoint: .bottomTrailing
                )
            )
            .overlay(
                TandemGlyph()
                    .stroke(Color.white, style: StrokeStyle(lineWidth: size * 0.105, lineCap: .round, lineJoin: .round))
            )
            .clipShape(RoundedRectangle(cornerRadius: size * 0.28, style: .continuous))
            .frame(width: size, height: size)
            .shadow(color: Color(hex: 0x6366F1).opacity(0.45), radius: size * 0.12, y: size * 0.045)
    }
}

/// A monochrome template image of the glyph for the menu bar (adapts to light/dark).
func tandemMenuBarImage() -> NSImage {
    let dim: CGFloat = 18
    let image = NSImage(size: NSSize(width: dim, height: dim))
    image.lockFocus()
    let path = NSBezierPath()
    path.lineWidth = 2.0
    path.lineCapStyle = .round
    path.lineJoinStyle = .round
    func p(_ x: CGFloat, _ y: CGFloat) -> NSPoint { NSPoint(x: x * dim, y: y * dim) }
    path.move(to: p(0.34, 0.24)); path.line(to: p(0.56, 0.50)); path.line(to: p(0.34, 0.76))
    path.move(to: p(0.54, 0.24)); path.line(to: p(0.76, 0.50)); path.line(to: p(0.54, 0.76))
    NSColor.black.setStroke()
    path.stroke()
    image.unlockFocus()
    image.isTemplate = true
    return image
}
