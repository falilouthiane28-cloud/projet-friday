// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "FridayVoice",
    platforms: [.macOS("26.0")],
    products: [
        .executable(name: "friday-voice", targets: ["FridayVoice"]),
        .executable(name: "friday-app", targets: ["FridayApp"]),
    ],
    targets: [
        // Logique pure (sans audio) : machine à états, wake word, barge-in, protocole.
        .target(name: "FridayVoiceCore"),
        // Logique pure de l'interface : machine d'états de l'avatar.
        .target(name: "FridayUICore"),
        // App SwiftUI : barre de menus, dashboard, overlay NSPanel (Liquid Glass), grille d'expressions.
        .executableTarget(name: "FridayApp", dependencies: ["FridayUICore"]),
        // Binaire : micro (AVAudioEngine + annulation d'écho), STT (SpeechAnalyzer), TTS (AVSpeechSynthesizer).
        .executableTarget(
            name: "FridayVoice",
            dependencies: ["FridayVoiceCore"],
            linkerSettings: [
                // Info.plist embarqué : descriptions d'usage du micro et de la reconnaissance vocale.
                .unsafeFlags(["-Xlinker", "-sectcreate", "-Xlinker", "__TEXT", "-Xlinker", "__info_plist",
                              "-Xlinker", "Support/Info.plist"]),
            ]
        ),
        // Vérifications du cœur (XCTest / Swift Testing absents des Command Line Tools) : `swift run friday-voice-checks`.
        .executableTarget(name: "friday-voice-checks", dependencies: ["FridayVoiceCore", "FridayUICore"], path: "Sources/FridayVoiceChecks"),
    ],
    swiftLanguageModes: [.v5]
)
