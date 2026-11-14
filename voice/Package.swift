// swift-tools-version: 6.0
import PackageDescription

/// Info.plist embarqué : descriptions d'usage du micro et de la reconnaissance vocale.
let embedInfoPlist: [LinkerSetting] = [
    .unsafeFlags(["-Xlinker", "-sectcreate", "-Xlinker", "__TEXT", "-Xlinker", "__info_plist",
                  "-Xlinker", "Support/Info.plist"]),
]

let package = Package(
    name: "FridayVoice",
    platforms: [.macOS("26.0")],
    products: [
        .executable(name: "friday-voice", targets: ["FridayVoice"]),
        .executable(name: "friday-app", targets: ["FridayApp"]),
    ],
    dependencies: [
        .package(url: "https://github.com/sindresorhus/KeyboardShortcuts", exact: "1.15.0"),
    ],
    targets: [
        // Logique pure (sans audio) : machine à états, wake word, barge-in, protocoles.
        .target(name: "FridayVoiceCore"),
        // Logique pure de l'interface : machine d'états de l'avatar, lien voix → avatar.
        .target(name: "FridayUICore", dependencies: ["FridayVoiceCore"]),
        // Audio réel partagé : micro (AVAudioEngine + annulation d'écho), STT (SpeechAnalyzer), TTS.
        .target(name: "FridayVoiceKit", dependencies: ["FridayVoiceCore"]),
        // App SwiftUI : barre de menus, dashboard, bulle NSPanel ; pipeline vocal dans le même processus,
        // cœur Python en sous-processus JSON Lines.
        .executableTarget(
            name: "FridayApp",
            dependencies: ["FridayUICore", "FridayVoiceKit", "KeyboardShortcuts"],
            linkerSettings: embedInfoPlist
        ),
        // Binaire autonome piloté par Python (`python -m friday --voice`).
        .executableTarget(name: "FridayVoice", dependencies: ["FridayVoiceCore", "FridayVoiceKit"],
                          linkerSettings: embedInfoPlist),
        // Vérifications du cœur (XCTest / Swift Testing absents des Command Line Tools) : `swift run friday-voice-checks`.
        .executableTarget(name: "friday-voice-checks", dependencies: ["FridayVoiceCore", "FridayUICore"], path: "Sources/FridayVoiceChecks"),
    ],
    swiftLanguageModes: [.v5]
)
