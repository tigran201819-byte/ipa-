import sys
import os
import json
import glob

app_name = sys.argv[1]
bundle_id = sys.argv[2]

os.makedirs("Sources", exist_ok=True)
os.makedirs("Assets.xcassets/AppIcon.appiconset", exist_ok=True)

icon_contents = {
    "images": [
        {
            "filename": "icon-1024.png",
            "idiom": "universal",
            "platform": "ios",
            "size": "1024x1024"
        }
    ],
    "info": {
        "author": "xcode",
        "version": 1
    }
}

found_icons = glob.glob("app_code/icon.*")
if found_icons:
    src = found_icons[0]
    os.system(f'sips -s format png -z 1024 1024 "{src}" --out Assets.xcassets/AppIcon.appiconset/icon-1024.png')
    os.system(f'sips -s format png -z 180 180 "{src}" --out app_code/AppIcon60x60@3x.png')

with open("Assets.xcassets/AppIcon.appiconset/Contents.json", "w") as f:
    json.dump(icon_contents, f, indent=2)

with open("Assets.xcassets/Contents.json", "w") as f:
    json.dump({"info": {"author": "xcode", "version": 1}}, f, indent=2)

swift_code = '''import UIKit
import WebKit

@main
class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        window = UIWindow(frame: UIScreen.main.bounds)
        window?.rootViewController = MainViewController()
        window?.makeKeyAndVisible()
        return true
    }
}

class MainViewController: UIViewController, WKScriptMessageHandler {
    var webView: WKWebView!

    override var preferredStatusBarStyle: UIStatusBarStyle {
        return .lightContent
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0.04, green: 0.02, blue: 0.09, alpha: 1.0)

        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "allowFileAccessFromFileURLs")
        config.userContentController.add(self, name: "nativeBuilder")

        webView = WKWebView(frame: view.bounds, configuration: config)
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        webView.backgroundColor = UIColor(red: 0.04, green: 0.02, blue: 0.09, alpha: 1.0)
        webView.isOpaque = false
        view.addSubview(webView)

        if let htmlPath = Bundle.main.path(forResource: "index", ofType: "html", inDirectory: "app_code") {
            let url = URL(fileURLWithPath: htmlPath)
            webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
        }
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "nativeBuilder",
              let payload = message.body as? [String: Any],
              let action = payload["action"] as? String else { return }

        if action == "buildIPA" {
            let appName = (payload["appName"] as? String) ?? "CustomApp"
            let bundleId = (payload["bundleId"] as? String) ?? "com.custom.app"
            let files = (payload["files"] as? [[String: String]]) ?? []
            let iconB64 = payload["iconBase64"] as? String

            DispatchQueue.global(qos: .userInitiated).async {
                do {
                    let ipaURL = try self.assembleIPAOnDevice(appName: appName, bundleId: bundleId, files: files, iconB64: iconB64)
                    DispatchQueue.main.async {
                        self.webView.evaluateJavaScript("onNativeBuildSuccess('\\(ipaURL.lastPathComponent)')")
                        self.shareFile(url: ipaURL)
                    }
                } catch {
                    let msg = error.localizedDescription.replacingOccurrences(of: "'", with: "")
                    DispatchQueue.main.async {
                        self.webView.evaluateJavaScript("onNativeBuildError('\\(msg)')")
                    }
                }
            }
        } else if action == "exportProject" {
            let filename = (payload["filename"] as? String) ?? "project.ipaproj"
            let jsonString = (payload["data"] as? String) ?? "{}"
            let docsDir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let fileURL = docsDir.appendingPathComponent(filename)
            try? jsonString.write(to: fileURL, atomically: true, encoding: .utf8)
            DispatchQueue.main.async {
                self.shareFile(url: fileURL)
            }
        }
    }

    func shareFile(url: URL) {
        let activityVC = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        if let popover = activityVC.popoverPresentationController {
            popover.sourceView = self.view
            popover.sourceRect = CGRect(x: self.view.bounds.midX, y: self.view.bounds.midY, width: 0, height: 0)
        }
        self.present(activityVC, animated: true)
    }

    func resizeImage(image: UIImage, size: CGSize) -> Data? {
        let renderer = UIGraphicsImageRenderer(size: size)
        let resized = renderer.image { _ in
            image.draw(in: CGRect(origin: .zero, size: size))
        }
        return resized.pngData()
    }

    func assembleIPAOnDevice(appName: String, bundleId: String, files: [[String: String]], iconB64: String?) throws -> URL {
        let fm = FileManager.default
        let workDir = fm.temporaryDirectory.appendingPathComponent("ipa_work_\\(UUID().uuidString)")
        try fm.createDirectory(at: workDir, withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: workDir) }

        let currentAppURL = Bundle.main.bundleURL
        let payloadDir = workDir.appendingPathComponent("Payload")
        try fm.createDirectory(at: payloadDir, withIntermediateDirectories: true)

        let cleanFolderName = appName.components(separatedBy: CharacterSet.alphanumerics.inverted).joined()
        let finalAppName = cleanFolderName.isEmpty ? "CustomApp" : cleanFolderName
        let targetAppURL = payloadDir.appendingPathComponent("\\(finalAppName).app")
        try fm.copyItem(at: currentAppURL, to: targetAppURL)

        let oldCodeDir = targetAppURL.appendingPathComponent("app_code")
        try? fm.removeItem(at: oldCodeDir)
        try fm.createDirectory(at: oldCodeDir, withIntermediateDirectories: true)

        for f in files {
            guard let relPath = f["path"], let content = f["content"] else { continue }
            let fileURL = oldCodeDir.appendingPathComponent(relPath)
            try fm.createDirectory(at: fileURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            try content.write(to: fileURL, atomically: true, encoding: .utf8)
        }

        // Жёсткая перезапись иконки во всех местах .app бандла для iOS и LiveContainer
        if let b64 = iconB64, let rawData = Data(base64Encoded: b64), let uiImg = UIImage(data: rawData) {
            try? fm.removeItem(at: targetAppURL.appendingPathComponent("Assets.car"))
            let iconNames = ["AppIcon60x60@2x.png", "AppIcon60x60@3x.png", "AppIcon76x76@2x~ipad.png", "Icon.png"]
            let iconSizes: [CGFloat] = [120, 180, 152, 1024]
            for (idx, name) in iconNames.enumerated() {
                if let png = resizeImage(image: uiImg, size: CGSize(width: iconSizes[idx], height: iconSizes[idx])) {
                    try? png.write(to: targetAppURL.appendingPathComponent(name))
                    try? png.write(to: oldCodeDir.appendingPathComponent(name))
                }
            }
        }

        let plistURL = targetAppURL.appendingPathComponent("Info.plist")
        if let plistData = try? Data(contentsOf: plistURL),
           var plistDict = try? PropertyListSerialization.propertyList(from: plistData, options: .mutableContainersAndLeaves, format: nil) as? [String: Any] {
            plistDict["CFBundleDisplayName"] = appName
            plistDict["CFBundleName"] = appName
            plistDict["CFBundleIdentifier"] = bundleId
            plistDict["CFBundleIconFiles"] = ["AppIcon60x60", "AppIcon76x76", "Icon"]
            plistDict["CFBundleIcons"] = [
                "CFBundlePrimaryIcon": [
                    "CFBundleIconFiles": ["AppIcon60x60", "Icon"],
                    "UIPrerenderedIcon": true
                ]
            ]
            if let newPlistData = try? PropertyListSerialization.data(fromPropertyList: plistDict, format: .xml, options: 0) {
                try newPlistData.write(to: plistURL)
            }
        }

        let docsDir = fm.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let outIPA = docsDir.appendingPathComponent("\\(finalAppName).ipa")
        try? fm.removeItem(at: outIPA)

        try PureSwiftZip.zipDirectory(sourceDir: workDir, destZip: outIPA)
        return outIPA
    }
}

class PureSwiftZip {
    static func zipDirectory(sourceDir: URL, destZip: URL) throws {
        let fm = FileManager.default
        var archiveData = Data()
        var centralDirectory = Data()
        var entryCount: UInt16 = 0

        let enumerator = fm.enumerator(at: sourceDir, includingPropertiesForKeys: [.isDirectoryKey], options: [])!
        for case let fileURL as URL in enumerator {
            let resourceValues = try fileURL.resourceValues(forKeys: [.isDirectoryKey])
            if resourceValues.isDirectory == true { continue }

            let relPath = fileURL.path.replacingOccurrences(of: sourceDir.path + "/", with: "")
            let nameData = relPath.data(using: .utf8)!
            let fileData = try Data(contentsOf: fileURL)
            let crc = crc32(data: fileData)
            let localOffset = UInt32(archiveData.count)

            var localHeader = Data()
            localHeader.appendUInt32(0x04034b50)
            localHeader.appendUInt16(20)
            localHeader.appendUInt16(0)
            localHeader.appendUInt16(0)
            localHeader.appendUInt16(0)
            localHeader.appendUInt16(0)
            localHeader.appendUInt32(crc)
            localHeader.appendUInt32(UInt32(fileData.count))
            localHeader.appendUInt32(UInt32(fileData.count))
            localHeader.appendUInt16(UInt16(nameData.count))
            localHeader.appendUInt16(0)
            localHeader.append(nameData)

            archiveData.append(localHeader)
            archiveData.append(fileData)

            var cdHeader = Data()
            cdHeader.appendUInt32(0x02014b50)
            cdHeader.appendUInt16(20)
            cdHeader.appendUInt16(20)
            cdHeader.appendUInt16(0)
            cdHeader.appendUInt16(0)
            cdHeader.appendUInt16(0)
            cdHeader.appendUInt16(0)
            cdHeader.appendUInt32(crc)
            cdHeader.appendUInt32(UInt32(fileData.count))
            cdHeader.appendUInt32(UInt32(fileData.count))
            cdHeader.appendUInt16(UInt16(nameData.count))
            cdHeader.appendUInt16(0)
            cdHeader.appendUInt16(0)
            cdHeader.appendUInt16(0)
            cdHeader.appendUInt16(0)
            cdHeader.appendUInt32(0)
            cdHeader.appendUInt32(localOffset)
            cdHeader.append(nameData)

            centralDirectory.append(cdHeader)
            entryCount += 1
        }

        let cdOffset = UInt32(archiveData.count)
        let cdSize = UInt32(centralDirectory.count)
        archiveData.append(centralDirectory)

        var eocd = Data()
        eocd.appendUInt32(0x06054b50)
        eocd.appendUInt16(0)
        eocd.appendUInt16(0)
        eocd.appendUInt16(entryCount)
        eocd.appendUInt16(entryCount)
        eocd.appendUInt32(cdSize)
        eocd.appendUInt32(cdOffset)
        eocd.appendUInt16(0)

        archiveData.append(eocd)
        try archiveData.write(to: destZip)
    }

    static func crc32(data: Data) -> UInt32 {
        var crc: UInt32 = 0xffffffff
        for byte in data {
            var b = UInt32(byte)
            for _ in 0..<8 {
                let mix = (crc ^ b) & 1
                crc >>= 1
                if mix != 0 { crc ^= 0xedb88320 }
                b >>= 1
            }
        }
        return ~crc
    }
}

extension Data {
    mutating func appendUInt16(_ value: UInt16) {
        var v = value.littleEndian
        append(Data(bytes: &v, count: 2))
    }
    mutating func appendUInt32(_ value: UInt32) {
        var v = value.littleEndian
        append(Data(bytes: &v, count: 4))
    }
}
'''

info_plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>ru</string>
    <key>CFBundleDisplayName</key>
    <string>{app_name}</string>
    <key>CFBundleExecutable</key>
    <string>$(EXECUTABLE_NAME)</string>
    <key>CFBundleIdentifier</key>
    <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
    <key>CFBundleIconFiles</key>
    <array>
        <string>AppIcon60x60</string>
    </array>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$(PRODUCT_NAME)</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSRequiresIPhoneOS</key>
    <true/>
    <key>UIFileSharingEnabled</key>
    <true/>
    <key>LSSupportsOpeningDocumentsInPlace</key>
    <true/>
    <key>UIUserInterfaceStyle</key>
    <string>Dark</string>
    <key>UILaunchScreen</key>
    <dict/>
</dict>
</plist>
'''

with open("Sources/App.swift", "w", encoding="utf-8") as f:
    f.write(swift_code)

with open("Sources/Info.plist", "w", encoding="utf-8") as f:
    f.write(info_plist)

project_yml = f'''name: {app_name}
options:
  bundleIdPrefix: com.custom
targets:
  {app_name}:
    type: application
    platform: iOS
    deploymentTarget: "15.0"
    sources:
      - path: Sources
        excludes:
          - Info.plist
      - path: Assets.xcassets
      - path: app_code
        type: folder
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: {bundle_id}
        INFOPLIST_FILE: Sources/Info.plist
        ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon
        GENERATE_INFOPLIST_FILE: NO
        ENABLE_BITCODE: NO
        CODE_SIGNING_ALLOWED: NO
'''

with open("project.yml", "w", encoding="utf-8") as f:
    f.write(project_yml)
