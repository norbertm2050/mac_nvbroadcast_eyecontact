import AppKit
import AVFoundation
import Darwin

final class AppDelegate: NSObject, NSApplicationDelegate {
    enum RunState { case stopped, authorizing, running, stopping }
    var state: RunState = .stopped
    var item: NSStatusItem!
    var worker: Process?
    var timer: Timer?
    var stopDeadline = Date.distantFuture
    var quitting = false
    var statusLine = NSMenuItem(title: "已停止", action: nil, keyEquivalent: "")
    var toggleItem = NSMenuItem(title: "启动眼神矫正", action: #selector(toggle), keyEquivalent: "")
    var settingsItem = NSMenuItem(title: "连接设置…", action: #selector(settings), keyEquivalent: ",")
    var window: NSWindow?
    var hostField = NSTextField()
    var portField = NSTextField()
    var tokenField = NSSecureTextField()
    var cameraPopup = NSPopUpButton()
    var config: [String: Any] = [:]
    let home = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("Remote Eye Contact")

    func applicationDidFinishLaunching(_ note: Notification) {
        NSApp.setActivationPolicy(.accessory)
        // LaunchServices generally coalesces launches; this also covers manual execution.
        let peers = NSRunningApplication.runningApplications(withBundleIdentifier: Bundle.main.bundleIdentifier ?? "")
        if peers.contains(where: {$0.processIdentifier != getpid() && !$0.isTerminated}) { NSApp.terminate(nil); return }
        for folder in [home,home.appendingPathComponent("logs"),home.appendingPathComponent("state")] {
            try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        }
        if let data = try? Data(contentsOf: home.appendingPathComponent("config.json")), let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any] { config = value }
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        item.button?.title = "○ Eye"
        let menu = NSMenu(); menu.autoenablesItems = false
        statusLine.isEnabled = false; menu.addItem(statusLine); menu.addItem(.separator())
        toggleItem.target = self; menu.addItem(toggleItem)
        settingsItem.target = self; menu.addItem(settingsItem)
        for (title, selector) in [("打开运行日志",#selector(logs)),("使用说明",#selector(help)),("退出",#selector(quit))] {
            let entry = NSMenuItem(title: title, action: selector, keyEquivalent: ""); entry.target = self; menu.addItem(entry)
        }
        item.menu = menu
        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in self?.refresh() }
        if (config["host"] as? String ?? "").isEmpty { settings() } else { start() }
    }

    func updateControls() {
        switch state {
        case .stopped: toggleItem.title = "启动眼神矫正"; toggleItem.isEnabled = true
        case .authorizing: toggleItem.title = "等待摄像头授权…"; toggleItem.isEnabled = false
        case .running: toggleItem.title = "停止眼神矫正"; toggleItem.isEnabled = true
        case .stopping: toggleItem.title = "正在停止…"; toggleItem.isEnabled = false
        }
        settingsItem.isEnabled = state == .stopped
    }

    @objc func toggle() { if state == .running { stop() } else if state == .stopped { start() } }
    func start() {
        guard state == .stopped, !quitting else { return }
        if (config["host"] as? String ?? "").isEmpty { settings(); return }
        state = .authorizing; updateControls()
        AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
            DispatchQueue.main.async {
                guard let self = self, !self.quitting else { return }
                if granted { self.launch() }
                else { self.state = .stopped; self.statusLine.title = "请在系统设置 → 隐私与安全性中允许摄像头访问"; self.item.button?.title = "! Eye"; self.updateControls() }
            }
        }
    }

    func launch() {
        let p = Process()
        p.executableURL = Bundle.main.resourceURL!.appendingPathComponent("Backend/eye-backend")
        p.arguments = ["--role", "mac"]; p.currentDirectoryURL = home
        var env = ProcessInfo.processInfo.environment
        for key in ["http_proxy","https_proxy","all_proxy","HTTP_PROXY","HTTPS_PROXY","ALL_PROXY"] { env.removeValue(forKey: key) }
        env["PYTHONUNBUFFERED"] = "1"; env["EYE_CONTACT_DATA_DIR"] = home.path; p.environment = env
        let file = home.appendingPathComponent("logs/native-camera.log")
        if let a = try? FileManager.default.attributesOfItem(atPath: file.path), let size = a[.size] as? NSNumber, size.intValue > 2_000_000 { try? FileManager.default.removeItem(at: file) }
        if !FileManager.default.fileExists(atPath: file.path) { FileManager.default.createFile(atPath: file.path, contents: nil, attributes: [.posixPermissions: 0o600]) }
        do {
            let handle = try FileHandle(forWritingTo: file); handle.seekToEndOfFile()
            p.standardOutput = handle; p.standardError = handle; p.standardInput = FileHandle.nullDevice
            try? FileManager.default.removeItem(at: home.appendingPathComponent("state/native-status.json"))
            p.terminationHandler = { [weak self] _ in DispatchQueue.main.async { self?.refresh() } }
            try p.run(); worker = p; state = .running; statusLine.title = "连接与预热中…"; item.button?.title = "… Eye"
            try? handle.close()
        } catch { state = .stopped; statusLine.title = "启动失败：\(error.localizedDescription)"; item.button?.title = "! Eye" }
        updateControls()
    }

    func refresh() {
        if let p = worker, !p.isRunning {
            let expected = state == .stopping || p.terminationStatus == 0
            state = .stopped; worker = nil
            statusLine.title = expected ? "已停止，摄像头已释放" : "启动失败或进程退出，请查看日志"
            item.button?.title = expected ? "○ Eye" : "! Eye"; updateControls()
        }
        if state == .stopping, let p = worker, p.isRunning, Date() > stopDeadline { kill(p.processIdentifier, SIGKILL) }
        if quitting && worker?.isRunning != true { NSApp.reply(toApplicationShouldTerminate: true); NSApp.terminate(nil); return }
        guard state == .running else { return }
        guard let data = try? Data(contentsOf: home.appendingPathComponent("state/native-status.json")), let s = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return }
        let phase = s["phase"] as? String ?? "starting"
        let names = ["ready":"眼神矫正已就绪 · 720p30","starting":"启动中…","connecting":"连接 Windows…","warming":"视频预热中…","reconnecting":"等待 Windows 视频…","stopped":"已停止","error":"启动失败，请查看日志"]
        statusLine.title = names[phase] ?? phase
        if phase != "ready", let message = s["networkMessage"] as? String, !message.isEmpty { statusLine.title = message }
        item.button?.title = phase == "ready" ? "◉ Eye" : (phase == "error" ? "! Eye" : "… Eye")
        if let updated = s["updated"] as? Double, Date().timeIntervalSince1970 - updated > 6 { statusLine.title = "等待摄像头或连接恢复…" }
    }

    func stop() {
        guard worker?.isRunning == true else { state = .stopped; updateControls(); return }
        state = .stopping; stopDeadline = Date().addingTimeInterval(7); worker?.terminate()
        statusLine.title = "正在停止并释放摄像头…"; updateControls()
    }

    @objc func settings() {
        guard state == .stopped else { return }
        if window == nil {
            let w = NSWindow(contentRect: NSRect(x:0,y:0,width:550,height:325), styleMask:[.titled,.closable], backing:.buffered, defer:false)
            w.title = "Remote Eye Contact · 连接设置"; w.isReleasedWhenClosed = false
            let content = w.contentView!
            func label(_ text: String, _ y: CGFloat) {
                let l = NSTextField(labelWithString:text); l.frame = NSRect(x:24,y:y,width:500,height:22); content.addSubview(l)
            }
            label("Windows 地址（局域网 IP 或 Tailscale 主机名）",277)
            hostField.frame = NSRect(x:24,y:246,width:395,height:26); hostField.placeholderString = "例如 192.168.1.100";content.addSubview(hostField)
            portField.frame = NSRect(x:431,y:246,width:94,height:26); portField.placeholderString = "8554"; content.addSubview(portField)
            label("连接码（复制 Windows 应用显示的连接码）",210)
            tokenField.frame = NSRect(x:24,y:180,width:500,height:26);content.addSubview(tokenField)
            label("Mac 摄像头",144)
            cameraPopup.frame = NSRect(x:24,y:110,width:500,height:28); content.addSubview(cameraPopup)
            label("固定输出 720p30；只处理视频。先启动 Windows 端服务。",70)
            let button = NSButton(title:"保存并启动",target:self,action:#selector(save));button.bezelStyle = .rounded; button.frame = NSRect(x:385,y:22,width:142,height:32);content.addSubview(button)
            window = w; w.center()
        }
        hostField.stringValue = config["host"] as? String ?? ""
        portField.stringValue = String(config["port"] as? Int ?? 8554)
        tokenField.stringValue = config["token"] as? String ?? ""
        cameraPopup.removeAllItems(); cameraPopup.addItem(withTitle:"默认摄像头"); cameraPopup.lastItem?.representedObject = "0"
        let devices = AVCaptureDevice.DiscoverySession(deviceTypes:[.builtInWideAngleCamera,.external],mediaType:.video,position:.unspecified).devices
        for device in devices where !device.localizedName.contains("OBS Virtual") {
            cameraPopup.addItem(withTitle:device.localizedName);cameraPopup.lastItem?.representedObject = device.localizedName
        }
        if let selected = config["camera"] as? String, let match = cameraPopup.itemArray.first(where: { $0.representedObject as? String == selected }) { cameraPopup.select(match) }
        window?.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps:true)
    }

    @objc func save() {
        let host = hostField.stringValue.trimmingCharacters(in:.whitespacesAndNewlines)
        let token = tokenField.stringValue.trimmingCharacters(in:.whitespacesAndNewlines)
        guard !host.isEmpty, host.range(of:"^[A-Za-z0-9.:-]+$",options:.regularExpression) != nil,
              let port = Int(portField.stringValue), (1024...65535).contains(port), token.range(of:"^[a-fA-F0-9]{32}$", options:.regularExpression) != nil else {
            let alert = NSAlert(); alert.messageText = "请检查连接设置"; alert.informativeText = "填写 IP 或主机名（不含协议和路径）、1024–65535 的端口，以及 Windows 上的 32 位连接码。"; alert.runModal(); return
        }
        config = ["host":host,"port":port,"token":token,"camera":cameraPopup.selectedItem?.representedObject as? String ?? "0"]
        do {
            let url = home.appendingPathComponent("config.json")
            try JSONSerialization.data(withJSONObject:config,options:[.prettyPrinted,.sortedKeys]).write(to:url,options:.atomic)
            try FileManager.default.setAttributes([.posixPermissions:0o600],ofItemAtPath:url.path)
            window?.orderOut(nil); start()
        } catch { let alert = NSAlert(error:error); alert.runModal() }
    }

    func applicationShouldHandleReopen(_ sender:NSApplication,hasVisibleWindows flag:Bool)->Bool {
        if state == .stopped { if (config["host"] as? String ?? "").isEmpty { settings() } else { start() } }; return true
    }
    @objc func logs() { NSWorkspace.shared.open(home.appendingPathComponent("logs")) }
    @objc func help() { NSWorkspace.shared.open(URL(string:"https://github.com/norbertm2050/mac_nvbroadcast_eyecontact#readme")!) }
    @objc func quit() { NSApp.terminate(nil) }
    func applicationShouldTerminate(_ sender:NSApplication)->NSApplication.TerminateReply {
        quitting = true
        if worker?.isRunning == true { stop(); return .terminateLater }
        return .terminateNow
    }
}
let app = NSApplication.shared
let delegate = AppDelegate(); app.delegate = delegate
app.run()
