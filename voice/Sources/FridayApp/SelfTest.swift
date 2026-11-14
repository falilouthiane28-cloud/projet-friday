import FridayUICore
import FridayVoiceCore
import Foundation

/// `friday-app --selftest` : chemin app ↔ cœur Python de bout en bout, sans écran ni micro.
/// Simule les événements du pipeline vocal et une saisie texte, vérifie l'avatar et le fil.
@MainActor
func runSelfTest() async -> Bool {
    let model = AppModel.shared
    var ok = true
    func check(_ cond: Bool, _ name: String) {
        print(cond ? "ok    \(name)" : "ÉCHEC \(name)")
        ok = ok && cond
    }
    func waitForReply(after count: Int) async -> Bool {
        for _ in 0..<100 where model.messages.count <= count { try? await Task.sleep(for: .milliseconds(50)) }
        return model.messages.count > count && model.messages.last?.fromFriday == true
    }

    model.startCore()
    model.handle(OutMessage(type: "state", state: "listening"))
    check(model.avatar == .listening && model.statusLabel == "À l'écoute", "écoute → « À l'écoute »")
    model.handle(OutMessage(type: "utterance", text: "quelle heure est il"))
    model.handle(OutMessage(type: "state", state: "processing"))
    check(model.statusLabel == "Je réfléchis", "réflexion → « Je réfléchis »")
    var n = model.messages.count
    check(model.messages.last?.text == "quelle heure est il" && model.messages.last?.fromFriday == false, "énoncé vocal dans le fil")
    check(await waitForReply(after: n), "réponse vocale du cœur : « \(model.messages.last?.text ?? "") »")
    model.handle(OutMessage(type: "state", state: "speaking"))
    check(model.statusLabel == "Je parle", "parole → « Je parle »")
    model.handle(OutMessage(type: "state", state: "idle"))
    try? await Task.sleep(for: .milliseconds(100))
    check(model.avatar == .neutral, "retour à neutre")

    model.draft = "quelle date sommes-nous"
    n = model.messages.count
    model.send()
    check(model.avatar == .thinking, "saisie texte → réflexion")
    check(await waitForReply(after: n + 1), "réponse texte du cœur : « \(model.messages.last?.text ?? "") »")
    model.shutdown()
    return ok
}
