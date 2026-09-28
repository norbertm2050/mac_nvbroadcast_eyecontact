import AppKit
import Foundation
let source = URL(fileURLWithPath: CommandLine.arguments[1])
let directory = URL(fileURLWithPath: CommandLine.arguments[2])
try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
guard let original = NSImage(contentsOf: source) else { fatalError("Cannot load generated icon") }
func png(_ size: Int) -> Data {
    let rep = NSBitmapImageRep(bitmapDataPlanes:nil,pixelsWide:size,pixelsHigh:size,bitsPerSample:8,samplesPerPixel:4,hasAlpha:true,isPlanar:false,colorSpaceName:.deviceRGB,bytesPerRow:0,bitsPerPixel:0)!
    let context = NSGraphicsContext(bitmapImageRep:rep)!
    NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.current = context
    context.imageInterpolation = .high
    original.draw(in:NSRect(x:0,y:0,width:size,height:size),from:.zero,operation:.copy,fraction:1)
    NSGraphicsContext.restoreGraphicsState()
    return rep.representation(using:.png,properties:[:])!
}
let iconset = directory.appendingPathComponent("AppIcon.iconset")
try FileManager.default.createDirectory(at: iconset, withIntermediateDirectories:true)
for base in [16,32,128,256,512] {
    try png(base).write(to:iconset.appendingPathComponent("icon_\(base)x\(base).png"))
    try png(base*2).write(to:iconset.appendingPathComponent("icon_\(base)x\(base)@2x.png"))
}
// Windows ICO container with PNG images; artwork is unchanged, only sizes/formats differ.
let sizes = [16,24,32,48,64,128,256]
let images = sizes.map { png($0) }
var ico = Data()
func u16(_ v:UInt16){ ico.append(UInt8(v & 255)); ico.append(UInt8(v >> 8)) }
func u32(_ v:UInt32){ for shift in [0,8,16,24] { ico.append(UInt8((v >> shift) & 255)) } }
u16(0);u16(1);u16(UInt16(sizes.count))
var offset = 6+16*sizes.count
for (size,data) in zip(sizes,images) {
    ico.append(size == 256 ? 0 : UInt8(size));ico.append(size == 256 ? 0 : UInt8(size));ico.append(0);ico.append(0)
    u16(1);u16(32);u32(UInt32(data.count));u32(UInt32(offset));offset += data.count
}
for data in images { ico.append(data) }
try ico.write(to:directory.appendingPathComponent("AppIcon.ico"))
