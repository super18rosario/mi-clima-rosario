"""Comprueba que la tarjeta de temperatura nunca use estimaciones."""
import pathlib
import unittest
BASE=pathlib.Path(__file__).resolve().parents[1]
class CurrentTemperatureUITests(unittest.TestCase):
    def test_temperature_shows_only_valid_inia_observations(self):
        content=(BASE/"index.html").read_text(encoding="utf-8")
        start=content.index("async function loadCurrent(){")
        end=content.index("function renderSkill(score){",start)
        logic=content[start:end]
        self.assertIn("getJson('./data/current_station.json')",logic)
        self.assertIn("station_id!==584",logic)
        self.assertIn("age > 120",logic)
        self.assertIn("value.textContent='— °C'",logic)
        self.assertIn("kind.textContent='Sin dato'",logic)
        self.assertNotIn("fetch(CURRENT_URL",logic)
        self.assertNotIn("Modelo Best Match",logic)
        self.assertNotIn("kind.textContent='Estimación'",logic)
    def test_initial_state_is_station_not_model(self):
        html=(BASE/"index.html").read_text(encoding="utf-8")
        fragment=html.split('<section class="now"',1)[1].split("</section>",1)[0]
        self.assertIn('id="now-source"',fragment)
        self.assertIn("INUMET / INIA La Estanzuela",fragment)
        self.assertNotIn("Open-Meteo",fragment)
if __name__=="__main__":
    unittest.main()
