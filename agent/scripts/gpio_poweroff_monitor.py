#!/usr/bin/env python3
"""
R1 / RK3588 GPIO Safe Poweroff Monitor Daemon
---------------------------------------------
Monitors a GPIO pin for a momentary push button (Option 1: GPIO to GND with internal pull-up).
When the button is held for a configurable duration (default: 1.5s), it performs a graceful
shutdown sequence:
  1. Stops all agent services (quickstart_all.sh stop) to save state and free NPU memory.
  2. Flushes filesystem dirty pages and buffers (sync; sync) to prevent disk corruption.
  3. Executes system poweroff via systemd (systemctl poweroff).

Also includes:
  --test : Simulation test mode (no actual shutdown, logs button events).
  --scan : Interactive pin scanner to detect which pin is pressed on the board.
"""

import argparse
import logging
import os
import signal
import subprocess
import sys
import time

CANDIDATE_PINS = [
    (39, "GPIO1_A7"),
    (36, "GPIO1_A4"),
    (61, "GPIO1_D5"),
    (41, "GPIO1_B1"),
    (0, "GPIO0_A0"),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("gpio_poweroff")


class SysfsGpioPin:
    """Manages a single GPIO pin via standard Linux /sys/class/gpio."""

    def __init__(self, pin: int, active_low: bool = True):
        self.pin = pin
        self.active_low = active_low
        self.base_path = f"/sys/class/gpio/gpio{pin}"
        self._exported_by_us = False

    def export(self):
        if not os.path.exists(self.base_path):
            try:
                with open("/sys/class/gpio/export", "w") as f:
                    f.write(str(self.pin))
                self._exported_by_us = True
                time.sleep(0.05)
            except Exception as e:
                logger.error(f"Failed to export GPIO {self.pin}: {e}")
                raise

        # Ensure direction is 'in'
        try:
            with open(f"{self.base_path}/direction", "w") as f:
                f.write("in")
        except Exception as e:
            logger.warning(f"Could not set direction for GPIO {self.pin}: {e}")

    def read_raw(self) -> int:
        with open(f"{self.base_path}/value", "r") as f:
            return int(f.read().strip())

    def is_pressed(self) -> bool:
        val = self.read_raw()
        return (val == 0) if self.active_low else (val == 1)

    def unexport(self):
        if self._exported_by_us and os.path.exists(self.base_path):
            try:
                with open("/sys/class/gpio/unexport", "w") as f:
                    f.write(str(self.pin))
                self._exported_by_us = False
            except Exception:
                pass


def perform_safe_shutdown(test_mode: bool = False, agent_root: str = "/userdata/agent", action: str = "halt"):
    """Executes the safe shutdown/halt sequence."""
    logger.info("==================================================")
    logger.info(f">>> INITIATING SAFE SYSTEM {action.upper()} SEQUENCE (MODE A) <<<")
    logger.info("==================================================")

    stop_script = os.path.join(agent_root, "scripts", "quickstart_all.sh")
    if os.path.isfile(stop_script):
        logger.info(f"[1/3] Gracefully stopping agent services via {stop_script} stop...")
        if not test_mode:
            try:
                subprocess.run(["bash", stop_script, "stop"], timeout=15, check=False)
            except Exception as e:
                logger.warning(f"Error stopping agent services: {e}")
    else:
        logger.info("[1/3] No agent stop script found; killing agent processes...")
        if not test_mode:
            subprocess.run(["pkill", "-f", "orchestrator.main"], check=False)
            subprocess.run(["pkill", "-f", "llm_daemon"], check=False)

    logger.info("[2/3] Flushing Linux filesystem caches to disk (sync)...")
    if not test_mode:
        try:
            os.system("sync; sync")
        except Exception as e:
            logger.warning(f"Sync error: {e}")

    logger.info(f"[3/3] Requesting system {action} (systemctl {action})...")
    if test_mode:
        logger.info(f"[TEST MODE] Simulation complete! System {action} skipped.")
        return

    try:
        subprocess.run(["systemctl", action], check=False)
    except Exception:
        # Fallback to halt/poweroff command
        os.system(f"{action} -f")


def run_monitor(pin_num: int, hold_time: float, debounce_time: float,
                poll_interval: float, test_mode: bool, active_low: bool,
                agent_root: str, action: str = "halt"):
    """Main loop monitoring the configured GPIO pin."""
    gpio = SysfsGpioPin(pin_num, active_low=active_low)
    try:
        gpio.export()
    except Exception as e:
        logger.error(f"Cannot initialize GPIO {pin_num}: {e}")
        sys.exit(1)

    running = True

    def signal_handler(signum, frame):
        nonlocal running
        logger.info(f"Received signal {signum}, exiting...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    initial_val = gpio.read_raw()
    logger.info(f"GPIO Poweroff Monitor started on GPIO {pin_num}.")
    logger.info(f"Config: hold_time={hold_time}s, debounce={debounce_time}s, "
                f"active_low={active_low}, test_mode={test_mode}, action={action}")
    logger.info(f"Current initial raw level on GPIO {pin_num}: {initial_val} "
                f"({'IDLE' if not gpio.is_pressed() else 'PRESSED'})")

    press_start_time = None
    triggered = False

    try:
        while running:
            pressed = gpio.is_pressed()
            now = time.time()

            if pressed:
                if press_start_time is None:
                    # Potential press detected, check debounce
                    time.sleep(debounce_time)
                    if gpio.is_pressed():
                        press_start_time = now
                        logger.info(f"[BUTTON] Pressed detected on GPIO {pin_num}, hold for {hold_time}s to {action}...")
                else:
                    elapsed = now - press_start_time
                    if elapsed >= hold_time and not triggered:
                        triggered = True
                        logger.info(f"[BUTTON] Held for {elapsed:.2f}s >= threshold {hold_time}s!")
                        # Wait for user to release the button first
                        logger.info("Waiting for button release before triggering shutdown...")
                        rel_start = time.time()
                        while gpio.is_pressed() and (time.time() - rel_start < 5.0):
                            time.sleep(0.05)
                        logger.info("Button released.")
                        perform_safe_shutdown(test_mode=test_mode, agent_root=agent_root, action=action)
                        if test_mode:
                            logger.info("[TEST MODE] Resetting trigger for continued testing.")
                            triggered = False
                            press_start_time = None
                        else:
                            # Break out to avoid re-triggering while shutting down
                            break
            else:
                if press_start_time is not None:
                    elapsed = now - press_start_time
                    if elapsed < hold_time and not triggered:
                        logger.info(f"[BUTTON] Released after {elapsed:.2f}s (< {hold_time}s). Ignored.")
                    press_start_time = None
                    triggered = False

            time.sleep(poll_interval)
    finally:
        logger.info(f"Cleaning up GPIO {pin_num}...")
        gpio.unexport()


def run_scanner(poll_interval: float = 0.05):
    """Scans all candidate pins and notifies user when any pin changes state."""
    logger.info("==================================================")
    logger.info("   INTERACTIVE GPIO PIN SCANNER FOR YOUYEETOO R1  ")
    logger.info("==================================================")
    logger.info("Watching candidate GPIO pins for button press or GND connection:")
    
    gpios = []
    baseline = {}
    for pin, name in CANDIDATE_PINS:
        try:
            g = SysfsGpioPin(pin, active_low=True)
            g.export()
            val = g.read_raw()
            baseline[pin] = val
            gpios.append((g, pin, name))
            logger.info(f"  • GPIO {pin:<2} ({name:<9}): Initial Raw Level = {val}")
        except Exception as e:
            logger.warning(f"  • GPIO {pin:<2} ({name:<9}): Could not export ({e})")

    if not gpios:
        logger.error("No GPIO pins could be exported. Check root permissions.")
        return

    logger.info("\n>>> Please touch or press your button between ANY pin and GND! <<<")
    logger.info("Press Ctrl+C to stop scanning.\n")

    running = True

    def signal_handler(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    active_press = {}

    try:
        while running:
            now = time.time()
            for g, pin, name in gpios:
                try:
                    val = g.read_raw()
                    # Triggered if active low (transition to 0 from 1)
                    if val != baseline[pin]:
                        if pin not in active_press:
                            active_press[pin] = now
                            logger.info(f"*** [TRIGGER DETECTED] Pin {pin} ({name}) changed: {baseline[pin]} -> {val} ! ***")
                        else:
                            held = now - active_press[pin]
                            if held >= 1.5:
                                logger.info(f"*** [HOLD 1.5s CONFIRMED] Pin {pin} ({name}) held for {held:.2f}s! Match confirmed! ***")
                                active_press[pin] = now + 1000  # Avoid spamming
                    else:
                        if pin in active_press:
                            del active_press[pin]
                            logger.info(f"    [RELEASED] Pin {pin} ({name}) restored to baseline {baseline[pin]}.")
                except Exception:
                    pass
            time.sleep(poll_interval)
    finally:
        logger.info("\nExiting scanner and cleaning up pins...")
        for g, _, _ in gpios:
            g.unexport()


def main():
    parser = argparse.ArgumentParser(description="RK3588 GPIO Safe Poweroff Monitor")
    parser.add_argument("--pin", type=int, default=39,
                        help="GPIO pin number (default: 39 for GPIO1_A7)")
    parser.add_argument("--hold-time", type=float, default=1.5,
                        help="Button hold duration in seconds (default: 1.5)")
    parser.add_argument("--debounce", type=float, default=0.1,
                        help="Debounce duration in seconds (default: 0.1)")
    parser.add_argument("--poll-interval", type=float, default=0.05,
                        help="Poll interval in seconds (default: 0.05)")
    parser.add_argument("--action", type=str, default="halt", choices=["halt", "poweroff"],
                        help="Shutdown action to execute: 'halt' (Mode A, stops and stays off) or 'poweroff' (default: halt)")
    parser.add_argument("--test", action="store_true",
                        help="Test mode: simulate shutdown without actually turning off")
    parser.add_argument("--scan", action="store_true",
                        help="Interactive scanner mode to find which pin is connected")
    parser.add_argument("--active-high", action="store_true",
                        help="Set active high (1 = pressed, default is active low: 0 = pressed)")
    parser.add_argument("--agent-root", type=str, default="/userdata/agent",
                        help="Root path of agent installation (default: /userdata/agent)")

    args = parser.parse_args()

    if args.scan:
        run_scanner(poll_interval=args.poll_interval)
    else:
        run_monitor(
            pin_num=args.pin,
            hold_time=args.hold_time,
            debounce_time=args.debounce,
            poll_interval=args.poll_interval,
            test_mode=args.test,
            active_low=not args.active_high,
            agent_root=args.agent_root,
            action=args.action,
        )


if __name__ == "__main__":
    main()
