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
import Compression

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
            if let htmlStr = try? String(contentsOf: url, encoding: .utf8) {
                webView.loadHTMLString(htmlStr, baseURL: url.deletingLastPathComponent())
            } else {
                webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
            }
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
        } else if action == "parseIPA" {
            guard let b64 = payload["data"] as? String,
                  let ipaData = Data(base64Encoded: b64) else { return }
            DispatchQueue.global(qos: .userInitiated).async {
                let result = self.extractIPA(data: ipaData)
                if let jsonData = try? JSONSerialization.data(withJSONObject: result, options: []),
                   let jsonStr = String(data: jsonData, encoding: .utf8) {
                    let escaped = jsonStr.replacingOccurrences(of: "\\\\", with: "\\\\\\\\").replacingOccurrences(of: "'", with: "\\\\'")
                    DispatchQueue.main.async {
                        self.webView.evaluateJavaScript("onIPAExtracted('\\(escaped)')")
                    }
                }
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

    func generateFallbackIcon(appName: String) -> UIImage {
        let size = CGSize(width: 512, height: 512)
        let format = UIGraphicsImageRendererFormat()
        format.opaque = true
        format.scale = 1.0
        return UIGraphicsImageRenderer(size: size, format: format).image { ctx in
            let colors = [
                UIColor(red: 0.45, green: 0.16, blue: 0.85, alpha: 1.0).cgColor,
                UIColor(red: 0.08, green: 0.04, blue: 0.18, alpha: 1.0).cgColor
            ] as CFArray
            if let gradient = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0.0, 1.0]) {
                ctx.cgContext.drawLinearGradient(gradient, start: CGPoint(x: 0, y: 0), end: CGPoint(x: 512, y: 512), options: [])
            }
            let letter = String(appName.prefix(1)).uppercased()
            let attrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 240, weight: .bold),
                .foregroundColor: UIColor.white
            ]
            let textSize = letter.size(withAttributes: attrs)
            let rect = CGRect(x: (512 - textSize.width) / 2, y: (512 - textSize.height) / 2, width: textSize.width, height: textSize.height)
            letter.draw(in: rect, withAttributes: attrs)
        }
    }

    func extractIPA(data: Data) -> [String: Any] {
        var extractedFiles: [[String: String]] = []
        var warnings: [String] = []
        var foundAppName = "ExtractedApp"
        var foundBundleId = "com.extracted.app"
        var foundIconB64 = ""

        let entries = PureSwiftZip.unzipEntries(data: data)
        if entries.isEmpty {
            return ["error": "Не удалось открыть архив IPA. Файл повреждён или зашифрован."]
        }

        let textExts = ["html", "htm", "js", "css", "py", "json", "txt", "xml", "plist", "lua", "swift", "c", "cpp", "h", "sh", "yml", "yaml"]

        for entry in entries {
            let name = entry.name
            if name.hasSuffix("/") { continue }

            if name.contains("SC_Info/") || name.hasSuffix(".sinf") || name.hasSuffix(".supf") {
                warnings.append("Обнаружена защита Apple FairPlay DRM: расшифровка бинарника невозможна.")
            }

            let fileName = (name as NSString).lastPathComponent
            let ext = (fileName as NSString).pathExtension.lowercased()

            if name.hasSuffix(".app/Info.plist") {
                if let plistDict = try? PropertyListSerialization.propertyList(from: entry.data, options: [], format: nil) as? [String: Any] {
                    if let dName = plistDict["CFBundleDisplayName"] as? String ?? plistDict["CFBundleName"] as? String {
                        foundAppName = dName
                    }
                    if let bId = plistDict["CFBundleIdentifier"] as? String {
                        foundBundleId = bId + ".copy"
                    }
                }
                continue
            }

            if (fileName.contains("AppIcon") || fileName.lowercased().contains("icon")) && ext == "png" && foundIconB64.isEmpty {
                if UIImage(data: entry.data) != nil {
                    foundIconB64 = entry.data.base64EncodedString()
                }
                continue
            }

            if name.contains("_CodeSignature/") || name.hasSuffix(".mobileprovision") || name.hasSuffix("Assets.car") || name.hasSuffix(".nib") {
                continue
            }

            if textExts.contains(ext) {
                if let text = String(data: entry.data, encoding: .utf8) {
                    var cleanPath = fileName
                    if let range = name.range(of: "app_code/") {
                        cleanPath = String(name[range.upperBound...])
                    } else if let range = name.range(of: ".app/") {
                        cleanPath = String(name[range.upperBound...])
                    }
                    extractedFiles.append([
                        "path": cleanPath,
                        "lang": ext,
                        "content": text
                    ])
                } else {
                    warnings.append("Не удалось загрузить код \\(fileName). Ошибка: расшифровка")
                }
            } else if ext.isEmpty || ext == "dylib" || ext == "framework" {
                if !fileName.hasPrefix("libswift") {
                    warnings.append("Не удалось загрузить код \\(fileName). Ошибка: расшифровка (скомпилированный / зашифрованный код)")
                }
            }
        }

        if extractedFiles.isEmpty {
            extractedFiles.append([
                "path": "index.html",
                "lang": "html",
                "content": "<!DOCTYPE html>\\n<html lang=\\"ru\\">\\n<head><meta charset=\\"UTF-8\\"></head>\\n<body style=\\"background:#090512;color:#fff;font-family:sans-serif;padding:20px;\\">\\n<h2>Импортированный пакет</h2>\\n<p>Открытый веб-код внутри IPA не найден (приложение скомпилировано в машинный код или зашифровано).</p>\\n</body>\\n</html>"
            ])
        }

        return [
            "appName": foundAppName,
            "bundleId": foundBundleId,
            "iconBase64": foundIconB64,
            "files": extractedFiles,
            "warnings": warnings
        ]
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

        // 1. Удаляем старую подпись и кэш ассетов родительского бандла
        try? fm.removeItem(at: targetAppURL.appendingPathComponent("_CodeSignature"))
        try? fm.removeItem(at: targetAppURL.appendingPathComponent("embedded.mobileprovision"))
        try? fm.removeItem(at: targetAppURL.appendingPathComponent("Assets.car"))

        let enumerator = fm.enumerator(at: targetAppURL, includingPropertiesForKeys: nil)
        while let fileURL = enumerator?.nextObject() as? URL {
            let name = fileURL.lastPathComponent
            if name.hasPrefix("AppIcon") || name.hasPrefix("Icon") {
                try? fm.removeItem(at: fileURL)
            }
        }

        let oldCodeDir = targetAppURL.appendingPathComponent("app_code")
        try? fm.removeItem(at: oldCodeDir)
        try fm.createDirectory(at: oldCodeDir, withIntermediateDirectories: true)

        for f in files {
            guard let relPath = f["path"], let content = f["content"] else { continue }
            let fileURL = oldCodeDir.appendingPathComponent(relPath)
            try fm.createDirectory(at: fileURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            try content.write(to: fileURL, atomically: true, encoding: .utf8)
        }

        // 2. Рендерим новую непрозрачную иконку во все стандартные имена iOS + внутрь проекта
        let sourceImg: UIImage
        if let b64 = iconB64, !b64.isEmpty, let rawData = Data(base64Encoded: b64), let uiImg = UIImage(data: rawData) {
            sourceImg = uiImg
        } else {
            sourceImg = generateFallbackIcon(appName: appName)
        }

        let format = UIGraphicsImageRendererFormat()
        format.opaque = true
        format.scale = 1.0

        let iconVariants: [(String, CGFloat)] = [
            ("AppIcon60x60@2x.png", 120),
            ("AppIcon60x60@3x.png", 180),
            ("Icon.png", 1024)
        ]

        for (fileName, dim) in iconVariants {
            let renderer = UIGraphicsImageRenderer(size: CGSize(width: dim, height: dim), format: format)
            let pngData = renderer.image { _ in
                sourceImg.draw(in: CGRect(x: 0, y: 0, width: dim, height: dim))
            }.pngData()
            if let data = pngData {
                try? data.write(to: targetAppURL.appendingPathComponent(fileName))
                if fileName == "Icon.png" {
                    // Сохраняем также в папку проекта как icon.png
                    try? data.write(to: oldCodeDir.appendingPathComponent("icon.png"))
                }
            }
        }

        // 3. Генерируем скрипт подключения иконки icon_config.js внутри проекта
        let iconScript = """
        window.APP_ICON_PATH = "./icon.png";
        (function() {
            var link = document.createElement('link');
            link.rel = 'apple-touch-icon';
            link.href = './icon.png';
            document.head.appendChild(link);
        })();
        """
        try? iconScript.write(to: oldCodeDir.appendingPathComponent("icon_config.js"), atomically: true, encoding: .utf8)

        // 4. Обновляем Info.plist под стандарт AppIcon60x60 (без расширения .png)
        let plistURL = targetAppURL.appendingPathComponent("Info.plist")
        if let plistData = try? Data(contentsOf: plistURL),
           var plistDict = try? PropertyListSerialization.propertyList(from: plistData, options: .mutableContainersAndLeaves, format: nil) as? [String: Any] {
            if let oldExec = plistDict["CFBundleExecutable"] as? String, oldExec != finalAppName {
                let oldExecURL = targetAppURL.appendingPathComponent(oldExec)
                let newExecURL = targetAppURL.appendingPathComponent(finalAppName)
                if fm.fileExists(atPath: oldExecURL.path) {
                    try? fm.moveItem(at: oldExecURL, to: newExecURL)
                    plistDict["CFBundleExecutable"] = finalAppName
                }
            }
            plistDict["CFBundleDisplayName"] = appName
            plistDict["CFBundleName"] = appName
            plistDict["CFBundleIdentifier"] = bundleId
            plistDict.removeValue(forKey: "CFBundleIconName")
            plistDict.removeValue(forKey: "CFBundleIcons~ipad")
            plistDict["CFBundleIconFile"] = "AppIcon60x60"
            plistDict["CFBundleIconFiles"] = ["AppIcon60x60"]
            plistDict["CFBundleIcons"] = [
                "CFBundlePrimaryIcon": [
                    "CFBundleIconFiles": ["AppIcon60x60"],
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

struct ZipEntry {
    let name: String
    let data: Data
}

class PureSwiftZip {
    static func unzipEntries(data: Data) -> [ZipEntry] {
        var results: [ZipEntry] = []
        let count = data.count
        if count < 22 { return results }

        var eocdOffset = -1
        for i in stride(from: count - 22, through: max(0, count - 65557), by: -1) {
            if data.readUInt32(at: i) == 0x06054b50 {
                eocdOffset = i
                break
            }
        }
        if eocdOffset == -1 { return results }

        let totalEntries = Int(data.readUInt16(at: eocdOffset + 10))
        var cdOffset = Int(data.readUInt32(at: eocdOffset + 16))

        for _ in 0..<totalEntries {
            if cdOffset + 46 > count || data.readUInt32(at: cdOffset) != 0x02014b50 { break }
            let compMethod = data.readUInt16(at: cdOffset + 10)
            let compSize = Int(data.readUInt32(at: cdOffset + 20))
            let uncompSize = Int(data.readUInt32(at: cdOffset + 24))
            let nameLen = Int(data.readUInt16(at: cdOffset + 28))
            let extraLen = Int(data.readUInt16(at: cdOffset + 30))
            let commentLen = Int(data.readUInt16(at: cdOffset + 32))
            let localHeaderOffset = Int(data.readUInt32(at: cdOffset + 42))

            if cdOffset + 46 + nameLen > count { break }
            let nameData = data.subdata(in: (cdOffset + 46)..<(cdOffset + 46 + nameLen))
            let name = String(data: nameData, encoding: .utf8) ?? ""

            if localHeaderOffset + 30 <= count {
                let lNameLen = Int(data.readUInt16(at: localHeaderOffset + 26))
                let lExtraLen = Int(data.readUInt16(at: localHeaderOffset + 28))
                let dataStart = localHeaderOffset + 30 + lNameLen + lExtraLen
                if dataStart + compSize <= count {
                    let compData = data.subdata(in: dataStart..<(dataStart + compSize))
                    if compMethod == 0 {
                        results.append(ZipEntry(name: name, data: compData))
                    } else if compMethod == 8, let decompressed = inflateRaw(data: compData, expectedSize: max(uncompSize, 1024)) {
                        results.append(ZipEntry(name: name, data: decompressed))
                    }
                }
            }
            cdOffset += 46 + nameLen + extraLen + commentLen
        }
        return results
    }

    static func inflateRaw(data: Data, expectedSize: Int) -> Data? {
        var outSize = max(expectedSize * 2, 65536)
        for _ in 0..<4 {
            var destBuffer = [UInt8](repeating: 0, count: outSize)
            let decodedCount = data.withUnsafeBytes { rawBuf -> Int in
                guard let srcPtr = rawBuf.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return 0 }
                return compression_decode_buffer(&destBuffer, outSize, srcPtr, data.count, nil, COMPRESSION_ZLIB)
            }
            if decodedCount > 0 && decodedCount < outSize {
                return Data(destBuffer.prefix(decodedCount))
            }
            outSize *= 4
        }
        return nil
    }

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
            cdHeader.appendUInt16(0x0314) // Unix + ZIP 2.0
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
            cdHeader.appendUInt32(0x81a40000) // Права доступа rw-r--r-- (0644) для LiveContainer
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
    func readUInt16(at offset: Int) -> UInt16 {
        return self.subdata(in: offset..<(offset + 2)).withUnsafeBytes { $0.load(as: UInt16.self).littleEndian }
    }
    func readUInt32(at offset: Int) -> UInt32 {
        return self.subdata(in: offset..<(offset + 4)).withUnsafeBytes { $0.load(as: UInt32.self).littleEndian }
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
