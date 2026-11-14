// Vérifications du cœur vocal. Lancer : swift run friday-voice-checks
import FridayVoiceCore
import FridayUICore

var failures = 0
var passed = 0
func check(_ cond: Bool, _ name: String, line: Int = #line) {
    if cond { passed += 1 } else { failures += 1; print("ÉCHEC l.\(line) : \(name)") }
}

// --- Wake word ---
let spotter = WakeWordSpotter()
check(spotter.commandAfterWakeWord(in: "Hey Friday, quelle heure est-il ?") == "quelle heure est il", "commande après wake word")
check(spotter.commandAfterWakeWord(in: "Hé FRIDAY") == "", "wake word seul")
check(spotter.commandAfterWakeWord(in: "quelle heure est-il") == nil, "pas de wake word")
check(normalizeSpeech("Éteins  la LUMIÈRE !") == "eteins la lumiere", "normalisation")

// --- Echo guard ---
check(EchoGuard.isLikelyEcho(heard: "il est dix heures", speaking: "Il est dix heures et quart."), "écho reconnu")
check(!EchoGuard.isLikelyEcho(heard: "stop arrête", speaking: "Il est dix heures et quart."), "vraie interruption")

// --- Scénario complet : "Hey Friday, quelle heure est-il ?" ---
var s = VoiceSession()
check(s.onTranscript("hey friday", now: 0) == [.state(.listening)], "idle → listening")
check(s.onTick(now: 0.5).isEmpty, "rien dit : on attend")
check(s.onTranscript("hey friday quelle heure", now: 1.0).isEmpty, "commande partielle")
check(s.onTranscript("hey friday quelle heure est-il", now: 1.3).isEmpty, "commande complète")
check(s.onTick(now: 1.6).isEmpty, "silence trop court")
check(s.onTick(now: 2.0).isEmpty, "0,7 s de silence : hésitation, on attend encore")
check(s.onTick(now: 2.5) == [.utterance("quelle heure est il"), .state(.processing), .resetTranscript], "fin d'énoncé → processing")
check(s.state == .processing, "état processing")
check(s.onSay("Il est dix heures.", now: 2.3) == [.state(.speaking), .speak("Il est dix heures."), .resetTranscript], "processing → speaking")
check(s.onSpeechFinished(now: 4) == [.state(.idle), .resetTranscript], "speaking → idle")

// --- Wake word et commande d'un seul souffle ---
var s2 = VoiceSession()
_ = s2.onTranscript("hey friday allume la lumiere", now: 0)
check(s2.state == .listening && s2.command == "allume la lumiere", "commande dans la même phrase")
check(s2.onTick(now: 1.2).first == .utterance("allume la lumiere"), "énoncé émis")

// --- Hésitation au milieu de la phrase (cas réel du 14/11) ---
var h = VoiceSession()
_ = h.onTranscript("friday aujourd'hui", now: 0)
check(h.onTick(now: 0.9).isEmpty, "pause de 0,9 s : la phrase continue")
_ = h.onTranscript("friday aujourd'hui on est le combien", now: 1.0)
check(h.onTick(now: 2.2).first == .utterance("aujourd'hui on est le combien"), "phrase entière envoyée")

// --- Timeout d'écoute ---
var s3 = VoiceSession()
_ = s3.onTranscript("friday", now: 0)
check(s3.onTick(now: 6.1) == [.state(.idle), .resetTranscript], "timeout d'écoute")

// --- Barge-in ---
var s4 = VoiceSession()
_ = s4.onSay("Voici la météo de la semaine à Paris.", now: 0)
check(s4.onTranscript("la météo", now: 0.5).isEmpty, "écho ignoré")
check(s4.onTranscript("stop", now: 0.6).isEmpty, "un seul mot ignoré")
check(s4.onTranscript("non arrête ça", now: 0.8) == [.stopSpeaking, .bargeIn, .state(.listening)], "barge-in")
check(s4.command == "non arrete ca", "commande reprise après barge-in")
check(s4.onTick(now: 2.0).first == .utterance("non arrete ca"), "la nouvelle commande part au cerveau")

// --- Stop et nouvelle réponse pendant qu'on parle ---
var s5 = VoiceSession()
_ = s5.onSay("Première phrase.", now: 0)
check(s5.onSay("Seconde.", now: 1).first == .stopSpeaking, "nouvelle réponse coupe l'ancienne")
check(s5.onStop(now: 2) == [.stopSpeaking, .state(.idle), .resetTranscript], "stop")

// --- Repos : tampon vidé, pas de déclenchement sans wake word ---
var s6 = VoiceSession()
check(s6.onTranscript("bonjour tout le monde", now: 0).isEmpty, "pas de wake word au repos")
check(s6.onTick(now: 2.1) == [.resetTranscript], "tampon vidé au repos")

// --- Protocole ---
check(InMessage.parse(#"{"type":"say","text":"Bonjour"}"#) == .say("Bonjour"), "say")
check(InMessage.parse(#"{"type":"stop"}"#) == .stop, "stop")
check(InMessage.parse("pas du json") == nil, "ligne invalide")
check(OutMessage(type: "metrics", ttfaMs: 420).jsonLine() == #"{"ttfa_ms":420,"type":"metrics"}"#, "json sortant")

// --- Avatar ---
var av = AvatarMachine()
check(AvatarState.allCases.count == 18, "18 états")
check(av.request(.happy, now: 0) == [.happy], "neutre → joyeux")
check(av.tick(now: 9.9).isEmpty && av.tick(now: 10) == [.neutral], "retour à neutre après 10 s")
_ = av.request(.sleeping, now: 20)
check(av.request(.angry, now: 21) == [.neutral, .angry], "endormi → colère passe par neutre")
check(av.request(.error, now: 22) == [.error], "erreur prioritaire")
check(av.request(.listening, now: 23).isEmpty && av.state == .error, "erreur non interrompue par l'écoute")
check(av.request(.alert, now: 24) == [.alert], "alerte remplace erreur")
check(av.clear(now: 25) == [.neutral], "clear")
_ = av.request(.listening, now: 26)
check(av.tick(now: 60).isEmpty, "l'écoute n'expire pas")

// --- Écoute manuelle (bouton micro, raccourci global) ---
var m = VoiceSession()
check(m.onListen(now: 0) == [.state(.listening), .resetTranscript], "idle → listening sans wake word")
check(m.onListen(now: 0.1).isEmpty, "déjà à l'écoute")
_ = m.onTranscript("quelle heure est-il", now: 0.5)
check(m.onTick(now: 1.7) == [.utterance("quelle heure est il"), .state(.processing), .resetTranscript], "commande sans wake word")
_ = m.onSay("Il est dix heures.", now: 2)
check(m.onListen(now: 2.5) == [.stopSpeaking, .state(.listening), .resetTranscript], "écoute coupe la parole")

// --- Protocole app ↔ cœur Python ---
check(CoreRequest.ask(id: 3, text: "Quelle heure ?", source: "text").jsonLine()
      == #"{"id":3,"source":"text","text":"Quelle heure ?","type":"ask"}"#, "ask encodé")
check(CoreRequest.metrics(ttfaMs: 420).jsonLine() == #"{"ttfa_ms":420,"type":"metrics"}"#, "metrics encodé")
check(CoreRequest.shutdown.jsonLine() == #"{"type":"shutdown"}"#, "shutdown encodé")
check(CoreEvent.parse(#"{"type":"ready","name":"FRIDAY"}"#) == .ready(name: "FRIDAY", brain: "local", claudeBinary: nil), "ready lu")
check(CoreEvent.parse(#"{"type":"ready","name":"FRIDAY","brain":"Claude Code","claude_binary":"/bin/claude"}"#)
      == .ready(name: "FRIDAY", brain: "Claude Code", claudeBinary: "/bin/claude"), "ready avec cerveau")
check(CoreEvent.parse(#"{"type":"reply","id":3,"text":"Il est 10 h.","intent":"general","agent":"conductor"}"#)
      == .reply(id: 3, text: "Il est 10 h.", intent: "general", agent: "conductor", loginRequired: false, streamed: false), "reply lu")
check(CoreEvent.parse(#"{"type":"reply","id":4,"text":"Connectez-vous.","login_required":true,"streamed":true}"#)
      == .reply(id: 4, text: "Connectez-vous.", intent: "", agent: "", loginRequired: true, streamed: true), "connexion requise lue")
check(CoreEvent.parse(#"{"type":"chunk","id":4,"text":"Première phrase."}"#) == .chunk(id: 4, text: "Première phrase."), "chunk lu")
check(CoreEvent.parse(#"{"type":"chunk","text":"sans id"}"#) == nil, "chunk sans id refusé")

// --- Réponse en flux : parler dès la première phrase ---
var f = VoiceSession()
_ = f.onListen(now: 0)
_ = f.onTranscript("raconte une histoire", now: 0.2)
_ = f.onTick(now: 1.5)
check(f.onSayMore("Il était une fois.", now: 2) == [.state(.speaking), .speak("Il était une fois."), .resetTranscript], "1re phrase : on parle tout de suite")
check(f.onSayMore("Un robot.", now: 2.5) == [.enqueueSpeech("Un robot.")], "phrases suivantes à la suite")
check(f.onTranscript("un robot", now: 2.8).isEmpty, "écho de la 2e phrase ignoré")
check(f.onSpeechFinished(now: 4) == [.state(.idle), .resetTranscript], "fin de la file → repos")
check(CoreRequest.reset.jsonLine() == #"{"type":"reset"}"#, "reset encodé")
check(CoreEvent.parse(#"{"type":"reply","text":"sans id"}"#) == nil, "reply sans id refusé")
check(CoreEvent.parse(#"{"type":"error","message":"boum"}"#) == .error("boum"), "error lu")
check(CoreEvent.parse("pas du json") == nil && CoreEvent.parse(#"{"type":"say"}"#) == nil, "messages inconnus ignorés")

// --- Confirmation Tier 1 ---
check(CoreEvent.parse(#"{"type":"confirm","id":2,"summary":"Supprimer vieux.txt","action":"file.delete"}"#)
      == .confirm(id: 2, summary: "Supprimer vieux.txt", action: "file.delete"), "confirm lu")
check(CoreEvent.parse(#"{"type":"confirm","summary":"sans id"}"#) == nil, "confirm sans id refusé")
check(CoreEvent.parse(#"{"type":"confirm","id":2,"summary":""}"#) == nil, "confirm sans résumé refusé")
check(CoreEvent.parse(#"{"type":"confirm_expired","id":2}"#) == .confirmExpired(id: 2), "confirm_expired lu")
check(CoreEvent.parse(#"{"type":"notice","text":"Rappel créé"}"#) == .notice("Rappel créé"), "notice lu")
check(CoreRequest.confirmResult(id: 2, ok: true).jsonLine() == #"{"id":2,"ok":true,"type":"confirm_result"}"#, "confirm_result encodé")
var card = ConfirmRequest(id: 2, summary: "Supprimer vieux.txt", action: "file.delete")
check(card.state == .pending && card.statusText == "En attente de votre accord", "carte en attente")
check(card.answer(false) == .confirmResult(id: 2, ok: false) && card.state == .denied, "Refuser → refus envoyé")
check(card.answer(true) == nil && card.state == .denied, "une seule réponse par carte")
card.expire()
check(card.state == .denied, "expiration sans effet après réponse")
var late = ConfirmRequest(id: 3, summary: "x", action: "")
late.expire()
check(late.state == .expired && late.answer(true) == nil, "carte expirée : plus de réponse possible")
check(ConfirmRequest(id: 4, summary: "Supprimer vieux.txt", action: "").spoken.contains("Supprimer vieux.txt"), "annonce vocale")

// --- Niveau audio ---
check(AudioLevel.normalized(rms: 0) == 0 && AudioLevel.normalized(rms: .nan) == 0, "silence → 0")
check(AudioLevel.normalized(rms: 0.001) == 0, "sous le plancher (-60 dB) → 0")
check(abs(AudioLevel.normalized(rms: 0.01) - 0.25) < 0.001, "-40 dB → 0,25")
check(AudioLevel.normalized(rms: 1) == 1, "plein niveau → 1")
check(AudioLevel.smoothed(previous: 0, target: 1) > AudioLevel.smoothed(previous: 1, target: 0) - 0.5, "montée plus rapide que la descente")
check(abs(AudioLevel.smoothed(previous: 1, target: 0) - 0.85) < 0.001, "descente lente")

// --- Racine du dépôt ---
let fakeRoot = URL(fileURLWithPath: "/depot")
check(findRepoRoot(from: URL(fileURLWithPath: "/depot/voice/.build/release")) { $0.path == "/depot/pyproject.toml" }?.path == fakeRoot.path, "racine trouvée en remontant")
check(findRepoRoot(from: URL(fileURLWithPath: "/ailleurs/bin")) { _ in false } == nil, "pas de racine")

// --- Voix → avatar ---
check(VoiceLink.avatar(for: .listening) == .listening && VoiceLink.avatar(for: .processing) == .thinking, "écoute et réflexion")
check(VoiceLink.avatar(for: .speaking) == .happy && VoiceLink.avatar(for: .idle) == nil, "parole, puis retour à neutre")
check(VoiceLink.label(voice: .speaking, avatar: .happy) == "Je parle", "libellé parole")
check(VoiceLink.label(voice: .listening, avatar: .listening) == "À l'écoute", "libellé écoute")
check(VoiceLink.label(voice: .processing, avatar: .thinking) == "Je réfléchis", "libellé réflexion")
check(VoiceLink.shouldSpeak(askedByVoice: true, speakAll: false, voiceAvailable: true), "question vocale → lue")
check(!VoiceLink.shouldSpeak(askedByVoice: false, speakAll: false, voiceAvailable: true), "message tapé → pas lu")
check(VoiceLink.shouldSpeak(askedByVoice: false, speakAll: true, voiceAvailable: true), "option tout lire")
check(!VoiceLink.shouldSpeak(askedByVoice: true, speakAll: true, voiceAvailable: false), "sans micro : rien")
check(VoiceLink.hotkey(expanded: false, voice: .idle) == .expandAndListen, "raccourci : bulle → fenêtre + écoute")
check(VoiceLink.hotkey(expanded: true, voice: .listening) == .stopListening, "raccourci : arrête l'écoute")
check(VoiceLink.hotkey(expanded: true, voice: .speaking) == .listen, "raccourci : coupe la parole et écoute")

// --- Mémoire : « Ce dont Friday se souvient… » ---
check(CoreRequest.memoryList.jsonLine() == #"{"type":"memory_list"}"#, "memory_list encodé")
check(CoreRequest.memoryForget(id: 7).jsonLine() == #"{"id":7,"type":"memory_forget"}"#, "memory_forget encodé")
let memLine = #"{"type":"memory","available":true,"facts":[{"id":2,"text":"La sœur de l'utilisateur s'appelle Awa","category":"proches","created_at":"2026-11-14T10:00:00+00:00"},{"id":1,"text":"L'utilisateur aime le jazz"},{"text":"sans id"}]}"#
if case .memory(let facts, let available, let forgot)? = CoreEvent.parse(memLine) {
    check(facts.count == 2 && available && forgot == nil, "memory lu (fait sans id ignoré)")
    check(facts[0].categoryLabel == "Proches" && facts[0].dayLabel == "14/11/2026", "catégorie et date lisibles")
    check(facts[1].categoryLabel == "Divers" && facts[1].dayLabel == "", "valeurs par défaut")
} else { check(false, "memory lu") }
check(CoreEvent.parse(#"{"type":"memory"}"#) == nil, "memory sans facts refusé")
check(CoreEvent.parse(#"{"type":"memory","facts":[],"available":false}"#) == .memory(facts: [], available: false, forgot: nil), "mémoire indisponible lue")
var book = MemoryBook()
check(book.open() == .memoryList && book.phase == .loading, "ouverture : liste demandée")
book.apply(facts: [MemoryFact(id: 1, text: "A"), MemoryFact(id: 2, text: "B")], available: true, forgot: nil)
check(book.phase == .loaded && book.facts.count == 2, "liste affichée")
check(book.tapForget(1) == nil && book.armed == 1, "1er appui : confirmation demandée")
check(book.tapForget(2) == nil && book.armed == 2, "autre fait : la confirmation change de fait")
check(book.tapForget(2) == .memoryForget(id: 2) && book.armed == nil, "2e appui : oubli envoyé")
check(book.tapForget(1) == nil && book.armed == nil, "un seul oubli à la fois")
book.apply(facts: [MemoryFact(id: 1, text: "A")], available: true, forgot: true)
check(book.facts.map(\.id) == [1] && book.lastMessage == "C'est oublié.", "fait retiré, message affiché")
check(book.tapForget(99) == nil, "fait inconnu ignoré")
_ = book.tapForget(1); book.cancel()
check(book.armed == nil, "annuler la confirmation")
book.apply(facts: [], available: false, forgot: nil)
check(book.phase == .unavailable && book.emptyText.contains("pas disponible"), "mémoire indisponible expliquée")

// Dashboard : données réelles du cœur
check(CoreRequest.dashboard.jsonLine() == #"{"type":"dashboard"}"#, "dashboard encodé")
if case .dashboard(let d)? = CoreEvent.parse(#"{"type":"dashboard","city":"Dakar","weather":{"city":"Dakar","temperature":27.4,"code":2,"label":"partiellement nuageux","is_day":false,"min":22,"max":30,"rain":5},"agenda":[{"start":"2026-11-14T14:00:00","end":"2026-11-14T15:00:00","title":"Dentiste","all_day":false},{"start":"2026-11-14T00:00:00","end":"2026-11-15T00:00:00","title":"Fête","all_day":true}],"agents":[{"name":"researcher","title":"Chercheur","role":"web","model":"sonnet","tools":["web_search"]}],"home_configured":false}"#) {
    check(d.weather?.city == "Dakar" && d.weather?.temperature == 27.4 && d.weather?.symbol == "cloud.moon", "météo lue (nuit : lune)")
    check(d.agenda?.map(\.timeLabel) == ["14:00", "Journée"], "agenda lu, heures")
    check(d.agents.first?.title == "Chercheur" && d.agents.first?.tools == ["web_search"], "agents lus")
    check(!d.homeConfigured && !d.unavailable, "domotique non configurée")
} else { check(false, "dashboard lu") }
if case .dashboard(let d)? = CoreEvent.parse(#"{"type":"dashboard","weather":null,"weather_error":"Météo indisponible (réseau).","agenda":null,"agenda_error":"Calendrier indisponible.","agents":[]}"#) {
    check(d.weather == nil && d.weatherError != nil && d.agenda == nil && d.agendaError != nil, "sources absentes avec raison")
} else { check(false, "dashboard partiel lu") }

print("\(passed) vérifications OK, \(failures) échec(s)")
if failures > 0 { exit(1) }

import Foundation
