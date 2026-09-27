import unittest

from adapter import build_config_payload, to_matter_state


class AdapterTest(unittest.TestCase):
    def test_config_describes_whole_home_electrical_meter(self):
        payload = build_config_payload()

        self.assertEqual(
            payload["deviceTypes"], ["OnOffPlugInUnit", "ElectricalSensor"]
        )
        basic_info = payload["clusters"]["BridgedDeviceBasicInformation"]
        self.assertEqual(basic_info["nodeLabel"], "Consumo total del hogar")
        self.assertIn("ElectricalPowerMeasurement", payload["clusters"])
        self.assertIn("ElectricalEnergyMeasurement", payload["clusters"])

    def test_measurements_are_converted_to_matter_units(self):
        state = to_matter_state(
            {
                "voltaje_V": 235.1,
                "corriente_A": 1.4,
                "potencia_W": 224.3,
                "energia_kWh": 15465.6,
            }
        )

        self.assertEqual(
            state["ElectricalPowerMeasurement"],
            {"voltage": 235100, "activeCurrent": 1400, "activePower": 224300},
        )
        self.assertEqual(
            state["ElectricalEnergyMeasurement"]["cumulativeEnergyImported"],
            {"energy": 15465600000},
        )


if __name__ == "__main__":
    unittest.main()
