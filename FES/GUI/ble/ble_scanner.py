from qt_core import *

class BLEScanner(QObject):
    updateStatus = Signal(str)
    updateNames = Signal(list)
    
    def __init__(self, parent: QObject = None, timeout=5000):
        super().__init__(parent)
        
        self.timeout = timeout
        self.scanner = QBluetoothDeviceDiscoveryAgent(self)
        self.devices = []
        
        self.scanner.setLowEnergyDiscoveryTimeout(self.timeout)
        
        self.scanner.deviceDiscovered.connect(self.on_device_discovered)        
        self.scanner.canceled.connect(self.on_scan_finished)
        self.scanner.finished.connect(self.on_scan_finished)
        self.scanner.errorOccurred.connect(self.on_scan_error)
        
    @Slot()
    def start_scanning(self):
        # Finished signal will be triggered when scan is finished (not stopped)
        self.scanner.start(QBluetoothDeviceDiscoveryAgent.DiscoveryMethod.LowEnergyMethod)
        self.updateStatus.emit("Scanning started...")
        
    def stop_scanning(self):
        # Cancel signal will be triggered when stop is called
        self.scanner.stop()
        self.updateStatus.emit("Scanning stopped.")
        
    def on_device_discovered(self, device: QBluetoothDeviceInfo):
        # Handle discovered device
        self.updateStatus.emit(f"Device discovered: {device.name()}")
        
    def on_scan_finished(self):
        # Save the scanned devices to a list
        self.devices = self.scanner.discoveredDevices()
        device_names = [device.name() for device in self.devices]
        self.updateNames.emit(device_names)
        self.updateStatus.emit("Scanning finished.")
        
    def on_scan_error(self, error):
        # Handle scan error
        if error == QBluetoothDeviceDiscoveryAgent.Error.PoweredOffError:
            error_msg = "Error: Bluetooth adaptor is off"
        elif error == QBluetoothDeviceDiscoveryAgent.Error.UnsupportedPlatformError:
            error_msg = "Error: BLE is not supported by this PC"
        elif error == QBluetoothDeviceDiscoveryAgent.Error.UnsupportedDiscoveryMethod:
            error_msg = "Error: Device discovery not supported by this PC"
        elif error == QBluetoothDeviceDiscoveryAgent.Error.InvalidBluetoothAdapterError:
            error_msg = "Error: Invalid Bluetooth adapter, please check your Bluetooth settings.\nMaybe the adapter is not enabled"
        else:
            error_msg = f"Error: Unknown error occurred, error code {error}"
            
        self.updateStatus.emit(error_msg)
        
    def get_devices(self) -> list[QBluetoothDeviceInfo]:
        # Return the list of scanned devices
        return self.devices
        