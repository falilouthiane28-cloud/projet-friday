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
check(s.onTick(now: 2.0) == [.utterance("quelle heure est il"), .state(.processing), .resetTranscript], "fin d'énoncé → processing")
check(s.state == .processing, "état processing")
check(s.onSay("Il est dix heures.", now: 2.3) == [.state(.speaking), .speak("Il est dix heures."), .resetTranscript], "processing → speaking")
check(s.onSpeechFinished(now: 4) == [.state(.idle), .resetTranscript], "speaking → idle")

// --- Wake word et commande d'un seul souffle ---
var s2 = VoiceSession()
_ = s2.onTranscript("hey friday allume la lumiere", now: 0)
check(s2.state == .listening && s2.command == "allume la lumiere", "commande dans la même phrase")
check(s2.onTick(now: 0.8).first == .utterance("allume la lumiere"), "énoncé émis")

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
check(s4.onTick(now: 1.6).first == .utterance("non arrete ca"), "la nouvelle commande part au cerveau")

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

print("\(passed) vérifications OK, \(failures) échec(s)")
if failures > 0 { exit(1) }

import Foundation
