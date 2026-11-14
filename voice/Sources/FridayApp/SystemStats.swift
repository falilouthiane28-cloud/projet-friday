import Darwin
import Foundation
import IOKit.ps
import Observation

/// CPU, mémoire, disque et batterie du Mac (API Mach, IOKit), rafraîchis toutes les 2 s.
@MainActor @Observable
final class SystemStats {
    private(set) var cpu: Double = 0
    private(set) var memory: Double = 0
    private(set) var disk: Double = 0
    private(set) var cpuHistory: [Double] = []          // 60 dernières mesures (2 min)
    private(set) var memoryUsedBytes: Double = 0
    let memoryTotalBytes = Double(ProcessInfo.processInfo.physicalMemory)
    private(set) var diskFreeBytes: Double = 0
    private(set) var diskTotalBytes: Double = 0
    private(set) var battery: Double?                   // nil : pas de batterie
    private(set) var charging = false
    var uptime: TimeInterval { ProcessInfo.processInfo.systemUptime }
    let cores = ProcessInfo.processInfo.activeProcessorCount
    private var previous: host_cpu_load_info?
    private var timer: Timer?

    init() {
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.refresh() }
        }
    }

    func refresh() {
        if let c = readCPU() {
            cpu = c
            cpuHistory.append(c)
            if cpuHistory.count > 60 { cpuHistory.removeFirst(cpuHistory.count - 60) }
        }
        memory = readMemory() ?? memory
        disk = readDisk() ?? disk
        readBattery()
    }

    private func readBattery() {
        guard let info = IOPSCopyPowerSourcesInfo()?.takeRetainedValue(),
              let list = IOPSCopyPowerSourcesList(info)?.takeRetainedValue() as? [CFTypeRef] else { battery = nil; return }
        for source in list {
            guard let d = IOPSGetPowerSourceDescription(info, source)?.takeUnretainedValue() as? [String: Any],
                  d[kIOPSTypeKey] as? String == kIOPSInternalBatteryType,
                  let cur = d[kIOPSCurrentCapacityKey] as? Int, let max = d[kIOPSMaxCapacityKey] as? Int, max > 0 else { continue }
            battery = Double(cur) / Double(max)
            charging = d[kIOPSIsChargingKey] as? Bool ?? false
            return
        }
        battery = nil
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
        memoryUsedBytes = used
        return used / memoryTotalBytes
    }

    private func readDisk() -> Double? {
        let url = URL(fileURLWithPath: "/")
        guard let v = try? url.resourceValues(forKeys: [.volumeTotalCapacityKey, .volumeAvailableCapacityForImportantUsageKey]),
              let total = v.volumeTotalCapacity, let free = v.volumeAvailableCapacityForImportantUsage, total > 0 else { return nil }
        diskFreeBytes = Double(free)
        diskTotalBytes = Double(total)
        return 1 - Double(free) / Double(total)
    }
}
