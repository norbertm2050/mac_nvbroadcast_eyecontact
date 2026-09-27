import Foundation
import AVFoundation
import CoreMediaIO

final class Probe:NSObject,AVCaptureVideoDataOutputSampleBufferDelegate {
    let session=AVCaptureSession()
    let file:FileHandle
    var count=0
    init(_ path:String) throws {
        if !FileManager.default.fileExists(atPath:path){FileManager.default.createFile(atPath:path,contents:nil)}
        file=try FileHandle(forWritingTo:URL(fileURLWithPath:path));file.seekToEndOfFile()
        super.init()
        var address=CMIOObjectPropertyAddress(mSelector:UInt32(kCMIOHardwarePropertyAllowScreenCaptureDevices),mScope:UInt32(kCMIOObjectPropertyScopeGlobal),mElement:UInt32(kCMIOObjectPropertyElementMain))
        var allow:UInt32=1
        CMIOObjectSetPropertyData(CMIOObjectID(kCMIOObjectSystemObject),&address,0,nil,4,&allow)
        let devices=AVCaptureDevice.DiscoverySession(deviceTypes:[.external,.builtInWideAngleCamera],mediaType:.video,position:.unspecified).devices
        guard let device=devices.first(where:{$0.localizedName.contains("OBS Virtual Camera")}) else {throw NSError(domain:"CameraProbe",code:1,userInfo:[NSLocalizedDescriptionKey:"Virtual camera missing: \(devices.map{$0.localizedName})"])}
        session.beginConfiguration()
        let input=try AVCaptureDeviceInput(device:device)
        session.addInput(input)
        let output=AVCaptureVideoDataOutput()
        output.alwaysDiscardsLateVideoFrames=true
        output.videoSettings=[kCVPixelBufferPixelFormatTypeKey as String:kCVPixelFormatType_32BGRA]
        output.setSampleBufferDelegate(self,queue:DispatchQueue(label:"probe"))
        session.addOutput(output)
        session.commitConfiguration();session.startRunning()
    }
    func captureOutput(_ output:AVCaptureOutput,didOutput sampleBuffer:CMSampleBuffer,from connection:AVCaptureConnection){
        guard let pixel=CMSampleBufferGetImageBuffer(sampleBuffer) else{return}
        CVPixelBufferLockBaseAddress(pixel,.readOnly)
        defer{CVPixelBufferUnlockBaseAddress(pixel,.readOnly)}
        guard let base=CVPixelBufferGetBaseAddress(pixel) else{return}
        let width=CVPixelBufferGetWidth(pixel),height=CVPixelBufferGetHeight(pixel),stride=CVPixelBufferGetBytesPerRow(pixel)
        let scale=Double(width)/1280.0
        let row=base.advanced(by:Int(8*scale)*stride).assumingMemoryBound(to:UInt8.self)
        func bright(_ x:Int)->Int {let p=Int(Double(x)*scale)*4;return (Int(row[p])+Int(row[p+1])+Int(row[p+2]))/3}
        if bright(6)>200 && bright(18)<60 {
            var stamp=0
            for i in 0..<24 {stamp=stamp*2+(bright((i+2)*12+6)>128 ? 1:0)}
            let now=Date().timeIntervalSince1970
            let age=(Int(now*1000)-stamp)%16777216
            if age<5000,let data=try? JSONSerialization.data(withJSONObject:["time":now,"ageMs":age,"width":width,"height":height]) {
                file.write(data);file.write(Data([10]));count+=1
            }
        }
    }
}
do {let probe=try Probe(CommandLine.arguments[1]);withExtendedLifetime(probe){RunLoop.main.run()}}
catch {fputs("\(error)\n",stderr);exit(1)}
