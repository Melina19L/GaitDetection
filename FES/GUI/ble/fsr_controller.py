from qt_core import *
import struct
from typing import Optional


class FSRController(QObject):
    """Manages BLE connection to an FSR peripheral on a dedicated thread."""

    # Signals
    updateStatus = Signal(str)
    updateConnected = Signal(bool)
    updateFSR = Signal(list)  # list[int] of length 3 (FF, MF, BF)
    busyChanged = Signal(bool)  # True while scanning/connecting/subscribing

    def __init__(self, foot: str):
        super().__init__()

        # Left or right
        self.foot = foot.lower().strip()
        if self.foot not in ("left", "right"):
            raise ValueError("Foot must be 'left' or 'right'.")

        # UUIDs per foot
        self.uuid = self.get_uuid(self.foot)
        self.fsr_characteristic = self.get_fsr_uuid(self.foot)

        # BLE state
        self.agent: Optional[QBluetoothDeviceDiscoveryAgent] = None
        self.imu_controller: Optional[QLowEnergyController] = None
        self.imu_service: Optional[QLowEnergyService] = None
        self.characteristic_fsr: Optional[QLowEnergyCharacteristic] = None
        self.imu_name: str = ""
        self.imu_services: list[QBluetoothUuid] = []

        # Thread bootstrap
        self._thread_ready = False
        self._pending_start_name: Optional[str] = None
        self._tearing_down = False
        self._busy = False  # add

    # -------------------------
    # Thread bootstrap
    # -------------------------

    @Slot()
    def start_in_thread(self):
        """Call this via QThread.started; initializes objects in the worker thread."""
        self._thread_ready = True
        self.updateStatus.emit("FSR worker thread ready.")
        # Late-create the discovery agent in this thread
        if self.agent is None:
            self.agent = QBluetoothDeviceDiscoveryAgent(self)
            try:
                self.agent.errorOccurred.connect(self._on_scan_error)  # type: ignore[attr-defined]
            except Exception:
                pass
            self.agent.deviceDiscovered.connect(self._on_device_found)
            self.agent.finished.connect(self._on_scan_finished)

        # Kick any queued connection request
        if self._pending_start_name:
            name = self._pending_start_name
            self._pending_start_name = None
            QTimer.singleShot(0, lambda: self.start_connect(name))

    # -------------------------
    # Public API
    # -------------------------

    @Slot(str)
    def start_connect(self, device_name: str):
        """Start scanning for the target and connect when found. Safe to call before thread is ready."""
        if not self._thread_ready:
            self._pending_start_name = device_name
            self.updateStatus.emit("Queued connection request (waiting for worker thread).")
            return

        if self._tearing_down:
            self.updateStatus.emit("Busy tearing down previous connection, try again shortly.")
            return
        if self._busy:
            self.updateStatus.emit("Already connecting; ignoring duplicate request.")
            return

        # Ensure clean state
        if self.imu_controller is not None:
            self.updateStatus.emit("Closing previous controller before connecting again.")
            self._teardown_controller()

        self._set_busy(True)
        self.target_name = device_name
        # Start scan
        try:
            # Use LowEnergy + Name filter first to reduce noise
            self.agent.setLowEnergyDiscoveryTimeout(8000)  # ms
        except Exception:
            pass
        self.updateStatus.emit(f"Scanning for '{device_name}'...")
        self.agent.start(QBluetoothDeviceDiscoveryAgent.DiscoveryMethod.LowEnergyMethod)
    
    # Adapter to match MainWindow signal signature (name, devices)
    @Slot(str, list)
    def connect_to_peripheral(self, device_name: str, _discovered_devices: list):
        """
        Compatibility slot: MainWindow emits (name, devices). We ignore the list
        and use the internal QBluetoothDeviceDiscoveryAgent-based scan.
        """
        self.start_connect(device_name)

    @Slot()
    def disconnect_from_peripheral(self):
        """Disconnect and clean up BLE objects safely."""
        if self.imu_controller:
            name = ""
            try:
                name = self.imu_controller.remoteName()
            except Exception:
                pass
            self.updateStatus.emit(f"Disconnecting from {name or 'device'}...")
            # Defer teardown until disconnect signal arrives
            try:
                self.imu_controller.disconnectFromDevice()
            except Exception:
                # If disconnect fails, force teardown
                QTimer.singleShot(0, self._teardown_controller)
        else:
            self.updateStatus.emit("No device connected.")

    # -------------------------
    # Scanner callbacks (run in worker thread)
    # -------------------------

    @Slot(QBluetoothDeviceInfo)
    def _on_device_found(self, dev: QBluetoothDeviceInfo):
        try:
            name = dev.name()
            addr = dev.address().toString()
        except Exception:
            return

        # Match by exact name or address
        if name == getattr(self, "target_name", "") or addr == getattr(self, "target_name", ""):
            self.updateStatus.emit(f"Found target: {name} ({addr}). Stopping scan...")
            try:
                self.agent.stop()
            except Exception:
                pass
            QTimer.singleShot(0, lambda d=dev: self._connect_device(d))

    @Slot()
    def _on_scan_finished(self):
        self.updateStatus.emit("Scan finished.")
        # If we didn’t start a controller, we’re done with this attempt
        if self.imu_controller is None:
            self._set_busy(False)

    @Slot(QBluetoothDeviceDiscoveryAgent.Error)
    def _on_scan_error(self, err: QBluetoothDeviceDiscoveryAgent.Error):
        self.updateStatus.emit(f"Scan error: {int(err)}")
        self._set_busy(False)

    # -------------------------
    # Connect & GATT (run in worker thread)
    # -------------------------

    def _connect_device(self, dev: QBluetoothDeviceInfo):
        # Create controller WITH parent=self so it lives in this worker thread
        self.imu_controller = QLowEnergyController.createCentral(dev, self)
        self.imu_controller.connected.connect(self.on_connected)
        self.imu_controller.disconnected.connect(self.on_disconnected)
        self.imu_controller.serviceDiscovered.connect(self.on_service_discovered)
        self.imu_controller.discoveryFinished.connect(self.on_discovery_finished)
        try:
            self.imu_controller.errorOccurred.connect(self.on_error)  # type: ignore[attr-defined]
        except Exception:
            try:
                self.imu_controller.error.connect(self.on_error)  # type: ignore[attr-defined]
            except Exception:
                pass

        self.updateStatus.emit("Connecting to device...")
        self.imu_controller.connectToDevice()

    @Slot()
    def on_connected(self):
        self.imu_services.clear()
        try:
            self.imu_name = self.imu_controller.remoteName() if self.imu_controller else ""
        except Exception:
            self.imu_name = ""
        self.updateConnected.emit(True)
        self.updateStatus.emit(f"Connected to {self.imu_name or 'device'}. Discovering services...")
        if self.imu_controller:
            self.imu_controller.discoverServices()

    @Slot()
    def on_disconnected(self):
        self.updateStatus.emit("BLE controller disconnected.")
        self.updateConnected.emit(False)
        # Defer teardown to avoid re-entrancy while Qt is still delivering signals
        QTimer.singleShot(0, self._teardown_controller)
        self._set_busy(False)

    @Slot(QBluetoothUuid)
    def on_service_discovered(self, service: QBluetoothUuid):
        self.imu_services.append(service)

    @Slot()
    def on_discovery_finished(self):
        if not self.imu_controller:
            self.updateStatus.emit("Discovery finished, but controller is missing.")
            self._set_busy(False)
            return

        # Create service object in this thread
        self.imu_service = self.imu_controller.createServiceObject(self.uuid, self)
        if not self.imu_service:
            self.updateStatus.emit(f"Service UUID {self.uuid.toString()} not found on device.")
            self._set_busy(False)
            return

        self.imu_service.stateChanged.connect(self.service_details_discovered)
        self.imu_service.characteristicChanged.connect(self.update_characteristic_values)

        # Discover all details
        self.imu_service.discoverDetails(QLowEnergyService.DiscoveryMode.FullDiscovery)

    @Slot(QLowEnergyService.ServiceState)
    def service_details_discovered(self, new_state: QLowEnergyService.ServiceState):
        if new_state == QLowEnergyService.ServiceState.RemoteServiceDiscovering:
            self.updateStatus.emit("Service details are being discovered...")
            return

        if new_state != QLowEnergyService.ServiceState.RemoteServiceDiscovered:
            return

        self.updateStatus.emit("Service details discovered.")

        # Fetch FSR characteristic
        self.characteristic_fsr = self.imu_service.characteristic(self.fsr_characteristic)
        if not self.characteristic_fsr.isValid():
            self.updateStatus.emit("Error: FSR characteristic not found.")
            self._set_busy(False)
            return

        # Enable notifications (0x0100)
        desc = self.characteristic_fsr.descriptor(QBluetoothUuid.DescriptorType.ClientCharacteristicConfiguration)
        if desc.isValid():
            try:
                self.imu_service.writeDescriptor(desc, QByteArray(bytearray.fromhex("0100")))
            except Exception as e:
                self.updateStatus.emit(f"Failed to enable notifications: {e}")
                self._set_busy(False)
                return

        self.updateStatus.emit("FSR characteristic subscribed.")
        # Connection workflow done
        self._set_busy(False)

    @Slot(QLowEnergyCharacteristic, QByteArray)
    def update_characteristic_values(self, characteristic: QLowEnergyCharacteristic, value: QByteArray):
        if not characteristic.isValid() or characteristic.uuid() != self.fsr_characteristic:
            return

        # Expect 4 bytes, first ignored, remaining map to BF, MF, FF (reverse to keep vector[0]=FF, [1]=MF, [2]=BF)
        try:
            if len(value) == 4:
                b0, bf, mf, ff = struct.unpack("<BBBB", bytes(value))
                self.updateFSR.emit([ff, mf, bf])
            else:
                self.updateStatus.emit(f"Unexpected FSR payload size: {len(value)}")
        except Exception as e:
            self.updateStatus.emit(f"FSR decode error: {e}")

    @Slot(int)
    def on_error(self, err: int):
        self.updateStatus.emit(f"BLE error: {err}")
        self._set_busy(False)

    # -------------------------
    # Helpers
    # -------------------------
    def _set_busy(self, b: bool):
        if self._busy != b:
            self._busy = b
            self.busyChanged.emit(b)

    def _teardown_controller(self):
        """Drop service/controller safely; created and destroyed in the same thread."""
        if self._tearing_down:
            return
        self._tearing_down = True
        try:
            # Stop notifications first
            try:
                if self.imu_service and self.characteristic_fsr and self.characteristic_fsr.isValid():
                    desc = self.characteristic_fsr.descriptor(QBluetoothUuid.DescriptorType.ClientCharacteristicConfiguration)
                    if desc.isValid():
                        self.imu_service.writeDescriptor(desc, QByteArray(bytearray.fromhex("0000")))
            except Exception:
                pass

            # Disconnect signals to avoid late deliveries into dead objects
            try:
                if self.imu_service:
                    self.imu_service.stateChanged.disconnect(self.service_details_discovered)
                    self.imu_service.characteristicChanged.disconnect(self.update_characteristic_values)
            except Exception:
                pass
            try:
                if self.imu_controller:
                    self.imu_controller.connected.disconnect(self.on_connected)
                    self.imu_controller.disconnected.disconnect(self.on_disconnected)
                    self.imu_controller.serviceDiscovered.disconnect(self.on_service_discovered)
                    self.imu_controller.discoveryFinished.disconnect(self.on_discovery_finished)
            except Exception:
                pass

            # Request disconnect if still connected
            try:
                if self.imu_controller:
                    self.imu_controller.disconnectFromDevice()
            except Exception:
                pass

            # Delete in-thread
            if self.imu_service:
                try:
                    self.imu_service.deleteLater()
                except Exception:
                    pass
            if self.imu_controller:
                try:
                    self.imu_controller.deleteLater()
                except Exception:
                    pass
        finally:
            self.imu_service = None
            self.characteristic_fsr = None
            self.imu_controller = None
            self.imu_services.clear()
            self._tearing_down = False
            self.updateStatus.emit("BLE objects torn down.")

    def get_uuid(self, foot: str) -> QBluetoothUuid:
        if foot == "left":
            return QBluetoothUuid(QUuid("00000000-0000-1000-8000-00805f9b34fc"))
        if foot == "right":
            return QBluetoothUuid(QUuid("00000000-0000-1000-8000-00805f9b34fd"))
        raise ValueError("Foot must be 'left' or 'right'.")

    def get_fsr_uuid(self, foot: str) -> QBluetoothUuid:
        if foot == "left":
            return QBluetoothUuid(QUuid("00000000-0000-1000-8000-00805f9b34fa"))
        if foot == "right":
            return QBluetoothUuid(QUuid("00000000-0000-1000-8000-00805f9b34fb"))
        raise ValueError("Foot must be 'left' or 'right'.")