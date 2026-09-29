import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import sys

# Add scripts directory to path
scripts_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

import gpio_poweroff_monitor as gpm


class TestGpioPoweroff(unittest.TestCase):

    def test_sysfs_gpio_pin_active_low(self):
        with patch("os.path.exists", return_value=True):
            pin = gpm.SysfsGpioPin(pin=39, active_low=True)
            with patch("builtins.open", mock_open(read_data="1\n")):
                self.assertEqual(pin.read_raw(), 1)
                self.assertFalse(pin.is_pressed())  # 1 is idle for active-low

            with patch("builtins.open", mock_open(read_data="0\n")):
                self.assertEqual(pin.read_raw(), 0)
                self.assertTrue(pin.is_pressed())  # 0 is pressed for active-low

    def test_sysfs_gpio_pin_active_high(self):
        with patch("os.path.exists", return_value=True):
            pin = gpm.SysfsGpioPin(pin=39, active_low=False)
            with patch("builtins.open", mock_open(read_data="1\n")):
                self.assertTrue(pin.is_pressed())  # 1 is pressed for active-high

            with patch("builtins.open", mock_open(read_data="0\n")):
                self.assertFalse(pin.is_pressed())

    @patch("subprocess.run")
    @patch("os.system")
    def test_safe_shutdown_test_mode(self, mock_system, mock_subproc):
        gpm.perform_safe_shutdown(test_mode=True, agent_root="/nonexistent")
        mock_subproc.assert_not_called()
        mock_system.assert_not_called()

    @patch("subprocess.run")
    @patch("os.system")
    @patch("os.path.isfile", return_value=True)
    def test_safe_shutdown_production_mode(self, mock_isfile, mock_system, mock_subproc):
        # Default action is halt (Mode A)
        gpm.perform_safe_shutdown(test_mode=False, agent_root="/userdata/agent", action="halt")
        calls = [c[0][0] for c in mock_subproc.call_args_list]
        self.assertIn(["bash", os.path.join("/userdata/agent", "scripts", "quickstart_all.sh"), "stop"], calls)
        self.assertIn(["systemctl", "halt"], calls)
        mock_system.assert_called_with("sync; sync")

        # Explicit action poweroff
        mock_subproc.reset_mock()
        gpm.perform_safe_shutdown(test_mode=False, agent_root="/userdata/agent", action="poweroff")
        calls_pwr = [c[0][0] for c in mock_subproc.call_args_list]
        self.assertIn(["systemctl", "poweroff"], calls_pwr)

    def test_candidate_pins_configuration(self):
        # Ensure GPIO1_A7 (pin 39) is among candidate pins
        pin_nums = [p[0] for p in gpm.CANDIDATE_PINS]
        self.assertIn(39, pin_nums)


if __name__ == "__main__":
    unittest.main()
