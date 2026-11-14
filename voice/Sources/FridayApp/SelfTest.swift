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

    // Confirmation Tier 1 : carte dans le fil, une seule réponse, expiration.
    model.overlayExpanded = true                  // pas de panneau en selftest
    model.handle(CoreEvent.confirm(id: 901, summary: "Supprimer vieux.txt", action: "file.delete"))
    check(model.messages.last?.confirm?.state == .pending, "carte Autoriser/Refuser dans le fil")
    model.answerConfirm(901, ok: true)
    check(model.messages.last?.confirm?.state == .allowed, "Autoriser → carte tranchée")
    model.answerConfirm(901, ok: false)
    check(model.messages.last?.confirm?.state == .allowed, "une seule réponse par carte")
    model.handle(CoreEvent.confirm(id: 902, summary: "Vider la corbeille", action: "file.delete"))
    model.handle(CoreEvent.confirmExpired(id: 902))
    check(model.messages.last?.confirm?.state == .expired, "sans réponse → refus affiché")
    model.handle(CoreEvent.notice("Créer le rappel « Appeler Paul »"))
    check(model.messages.last?.isNotice == true, "notification Tier 2 dans le fil")
    model.shutdown()
    return ok
}
