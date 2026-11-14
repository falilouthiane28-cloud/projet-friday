import Darwin
import Foundation
import Observation

/// CPU, mémoire et disque du Mac (API Mach), rafraîchis toutes les 2 s.
@MainActor @Observable
final class SystemStats {
    private(set) var cpu: Double = 0
    private(set) var memory: Double = 0
    private(set) var disk: Double = 0
    private var previous: host_cpu_load_info?
    private var timer: Timer?

    init() {
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.refresh() }
        }
    }

    func refresh() {
        cpu = readCPU() ?? cpu
        memory = readMemory() ?? memory
        disk = readDisk() ?? disk
    }

    private func readCPU() -> Double? {
        var info = host_cpu_load_info()
        var count = mach_msg_type_number_t(MemoryLayout<host_cpu_load_info>.size / MemoryLayout<integer_t>.size)
        let kr = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { host_statistics(mach_host_self(), HOST_CPU_LOAD_INFO, $0, &count) }
        }
        guard kr == KERN_SUCCESS else { return nil }
        defer { previous = info }
        guard let p = previous else { return nil }
        let t = info.cpu_ticks, q = p.cpu_ticks
        let user = Double(t.0 &- q.0), sys = Double(t.1 &- q.1), idle = Double(t.2 &- q.2), nice = Double(t.3 &- q.3)
        let total = user + sys + idle + nice
        return total > 0 ? (user + sys + nice) / total : nil
    }

    private func readMemory() -> Double? {
        var stats = vm_statistics64()
        var count = mach_msg_type_number_t(MemoryLayout<vm_statistics64>.size / MemoryLayout<integer_t>.size)
        let kr = withUnsafeMutablePointer(to: &stats) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { host_statistics64(mach_host_self(), HOST_VM_INFO64, $0, &count) }
        }
        guard kr == KERN_SUCCESS else { return nil }
        let used = Double(stats.active_count + stats.wire_count + stats.compressor_page_count) * Double(vm_kernel_page_size)
        return used / Double(ProcessInfo.processInfo.physicalMemory)
    }

    private func readDisk() -> Double? {
        let url = URL(fileURLWithPath: "/")
        guard let v = try? url.resourceValues(forKeys: [.volumeTotalCapacityKey, .volumeAvailableCapacityForImportantUsageKey]),
              let total = v.volumeTotalCapacity, let free = v.volumeAvailableCapacityForImportantUsage, total > 0 else { return nil }
        return 1 - Double(free) / Double(total)
    }
}
